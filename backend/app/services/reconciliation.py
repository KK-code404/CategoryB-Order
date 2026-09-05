from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LedgerEntry, LedgerType, MaterialMapping, OutboundMail, SalesOrderLine, ShipmentLine, ShipmentStatus, Supplier, User
from .audit import add_audit_event


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 生成供应商可直接执行的发货指令正文，并避免在邮件中遗漏地址与联系电话。
def _build_mail_body(supplier: Supplier, lines: list[ShipmentLine], correction: bool = False) -> str:
    heading = "发货撤销/更正通知" if correction else "发货指令"
    content = [f"{supplier.name}：", "", f"以下为平台确认的{heading}，请按明细处理：", ""]
    for line in lines:
        prefix = "撤销" if correction else "发货"
        content.append(f"- {prefix} | 订单 {line.order_no} | 物料 {line.material_no} | 零件 {line.part_no} | 数量 {line.quantity} | {line.receiver} {line.phone} {line.address} | 日期 {line.requested_ship_date}")
    content.extend(["", "此邮件由油品发货核销平台自动发送，请勿直接修改邮件明细。"])
    return "\n".join(content)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 在同一事务中锁定订单、扣减余额、写入流水与外发箱，防止并发超扣和漏发指令。
def confirm_lines(db: Session, actor: User, line_ids: list[int], ip_address: str) -> tuple[int, int]:
    lines = db.scalars(select(ShipmentLine).where(ShipmentLine.id.in_(line_ids)).with_for_update()).all()
    if len(lines) != len(set(line_ids)):
        raise HTTPException(status_code=404, detail="部分发货明细不存在")

    supplier_groups: dict[int, list[ShipmentLine]] = defaultdict(list)
    for line in lines:
        if line.status != ShipmentStatus.PENDING or not line.matched_order_line_id:
            raise HTTPException(status_code=409, detail=f"明细 {line.id} 当前不可核销")
        order_line = db.scalar(select(SalesOrderLine).where(SalesOrderLine.id == line.matched_order_line_id).with_for_update())
        if not order_line:
            raise HTTPException(status_code=409, detail="匹配订单已不存在")
        remaining = Decimal(order_line.ordered_qty) - Decimal(order_line.reconciled_qty)
        if Decimal(line.quantity) > remaining:
            line.status = ShipmentStatus.EXCEPTION
            line.exception_reason = f"并发校验失败：剩余未发数量仅 {remaining}"
            raise HTTPException(status_code=409, detail=line.exception_reason)

        order_line.reconciled_qty = Decimal(order_line.reconciled_qty) + Decimal(line.quantity)
        order_line.version += 1
        line.status = ShipmentStatus.RECONCILED
        ledger = LedgerEntry(shipment_line_id=line.id, order_line_id=order_line.id, entry_type=LedgerType.DEBIT, quantity=line.quantity, actor_id=actor.id, reason="确认发货核销")
        db.add(ledger)
        mapping = db.scalar(select(MaterialMapping).where(MaterialMapping.material_no == line.material_no))
        if not mapping:
            raise HTTPException(status_code=409, detail=f"物料 {line.material_no} 缺少供应商映射")
        supplier_groups[mapping.supplier_id].append(line)
        add_audit_event(db, actor=actor, action="核销", object_type="ShipmentLine", object_id=str(line.id), detail=f"核销物料 {line.material_no} 数量 {line.quantity}，核销后余额 {order_line.ordered_qty - order_line.reconciled_qty}", dealer_id=line.request.dealer_id, ip_address=ip_address)

    mail_count = 0
    for supplier_id, grouped_lines in supplier_groups.items():
        supplier = db.get(Supplier, supplier_id)
        assert supplier
        key_material = ",".join(str(line.id) for line in sorted(grouped_lines, key=lambda item: item.id))
        key = hashlib.sha256(f"SHIPMENT:{key_material}".encode()).hexdigest()
        db.add(OutboundMail(supplier_id=supplier.id, recipient=supplier.email, subject=f"[发货指令] {grouped_lines[0].request.request_no}", body=_build_mail_body(supplier, grouped_lines), line_ids_json=json.dumps([line.id for line in grouped_lines]), idempotency_key=key))
        mail_count += 1
    db.commit()
    return len(lines), mail_count


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 通过反向流水恢复订单余额，并在原指令已发出后创建供应商更正通知。
def reverse_line(db: Session, actor: User, line: ShipmentLine, reason: str, ip_address: str) -> ShipmentLine:
    if line.status != ShipmentStatus.RECONCILED or not line.matched_order_line_id:
        raise HTTPException(status_code=409, detail="只有已核销明细可以冲销")
    order_line = db.scalar(select(SalesOrderLine).where(SalesOrderLine.id == line.matched_order_line_id).with_for_update())
    original = db.scalar(select(LedgerEntry).where(LedgerEntry.shipment_line_id == line.id, LedgerEntry.entry_type == LedgerType.DEBIT))
    if not order_line or not original:
        raise HTTPException(status_code=409, detail="原核销流水不完整，禁止自动冲销")
    if db.scalar(select(LedgerEntry).where(LedgerEntry.reverses_entry_id == original.id)):
        raise HTTPException(status_code=409, detail="该核销已经冲销")

    order_line.reconciled_qty = Decimal(order_line.reconciled_qty) - Decimal(line.quantity)
    order_line.version += 1
    line.status = ShipmentStatus.REVERSED
    db.add(LedgerEntry(shipment_line_id=line.id, order_line_id=order_line.id, entry_type=LedgerType.REVERSAL, quantity=line.quantity, actor_id=actor.id, reason=reason, reverses_entry_id=original.id))

    mapping = db.scalar(select(MaterialMapping).where(MaterialMapping.material_no == line.material_no))
    if mapping and line.request.uid_validity != 'approved-history':
        supplier = db.get(Supplier, mapping.supplier_id)
        assert supplier
        key = hashlib.sha256(f"CORRECTION:{line.id}:{original.id}".encode()).hexdigest()
        db.add(OutboundMail(supplier_id=supplier.id, kind="CORRECTION", recipient=supplier.email, subject=f"[发货更正] {line.request.request_no}", body=_build_mail_body(supplier, [line], correction=True), line_ids_json=json.dumps([line.id]), idempotency_key=key))
    add_audit_event(db, actor=actor, action="冲销", object_type="ShipmentLine", object_id=str(line.id), detail=f"冲销数量 {line.quantity}；原因：{reason}", dealer_id=line.request.dealer_id, ip_address=ip_address)
    db.commit()
    db.refresh(line)
    return line

