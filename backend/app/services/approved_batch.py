"""Explicit administrator-approved promotion, invoked by the deployment CLI only.

Not exposed as an HTTP mutation. The caller owns commit/rollback. The original
simulation evidence remains in private storage and the immutable import/audit
records; this is approval to account for it, not evidence of carrier delivery.
"""
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ImportJob, LedgerEntry, LedgerType, SalesOrderLine, ShipmentLine, ShipmentRequest, ShipmentStatus, User, UserRole
from .audit import add_audit_event
from .reconciliation_analytics import CUTOFF, EXCLUDED_ORDERS, IMPORT_TOKEN, PROMOTION_TOKEN, SIM_END, reconciliation_analytics


def promote_approved_batch(db: Session, actor: User, approved_events: list[dict]) -> dict:
    if actor.role != UserRole.ADMIN or not actor.active:
        raise HTTPException(403, "仅管理员可执行已批准的历史补录")
    # Existing snapshot row serializes concurrent invocations on PostgreSQL.
    source = db.scalar(select(ImportJob).where(ImportJob.token == IMPORT_TOKEN,
                                              ImportJob.committed_at.is_not(None)).with_for_update())
    if not source:
        raise HTTPException(409, "缺少已提交的原始历史快照")
    canonical = json.dumps(sorted(approved_events, key=lambda e: e['id']), sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    evidence_hash = hashlib.sha256(canonical.encode()).hexdigest()
    existing = db.scalar(select(ImportJob).where(ImportJob.token == PROMOTION_TOKEN))
    if existing:
        result = json.loads(existing.payload_json)
        if not existing.committed_at or result['evidence_sha256'] != evidence_hash:
            raise HTTPException(409, "批次已存在但证据不一致，禁止重复补录")
        return {**result['result'], 'already_applied': True}

    expected = reconciliation_analytics(db, actor, date(2026, 8, 27), SIM_END)['simulation']['events']
    expected_canonical = json.dumps(sorted(expected, key=lambda e: e['id']), sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    if not approved_events or canonical != expected_canonical:
        raise HTTPException(409, "待入账明细与获批模拟批次不一致")
    ids = sorted({event['order_line_id'] for event in approved_events})
    orders = {o.id: o for o in db.scalars(select(SalesOrderLine).where(SalesOrderLine.id.in_(ids))
                                         .order_by(SalesOrderLine.id).with_for_update()).all()}
    if len(orders) != len(ids):
        raise HTTPException(409, "部分订单行已不存在")
    required = defaultdict(Decimal)
    for event in approved_events:
        order = orders[event['order_line_id']]
        quantity = Decimal(event['quantity'])
        day = date.fromisoformat(event['date'])
        if order.order_no.strip() in EXCLUDED_ORDERS or order.unit != '桶' or not CUTOFF < day <= SIM_END or quantity <= 0:
            raise HTTPException(409, "批次含排除订单、未确认单位、非法日期或数量")
        required[order.id] += quantity
    for order_id, quantity in required.items():
        order = orders[order_id]
        if order.ordered_qty - order.reconciled_qty < quantity:
            raise HTTPException(409, f"订单 {order.order_no}/{order.part_no} 当前剩余不足，本批次未入账")

    now = datetime.now(timezone.utc)
    requests = {}
    line_ids = []
    for event in sorted(approved_events, key=lambda e: (e['date'], e['order_line_id'])):
        order = orders[event['order_line_id']]
        key = (order.dealer_id, event['date'])
        if key not in requests:
            request_no = f"ADJ-{event['date'].replace('-', '')}-{order.dealer.code}"
            request = ShipmentRequest(
                request_no=request_no, dealer_id=order.dealer_id, sender_email='',
                subject=f"经用户确认的发货补录（非邮件） {event['date']}", batch_no=PROMOTION_TOKEN,
                message_id=f"{PROMOTION_TOKEN}/{order.dealer_id}/{event['date']}", imap_uid='manual',
                uid_validity='approved-history', attachment_name='approved-20260827-20260903.json',
                attachment_sha256=evidence_hash,
                attachment_path=f"historical-imports/{PROMOTION_TOKEN}/approved-20260827-20260903.json",
                received_at=now,
            )
            db.add(request)
            db.flush()
            requests[key] = request
        quantity = Decimal(event['quantity'])
        before = order.ordered_qty - order.reconciled_qty
        line = ShipmentLine(
            request_id=requests[key].id, row_fingerprint=hashlib.sha256(f"{PROMOTION_TOKEN}/{event['id']}".encode()).hexdigest(),
            order_no=order.order_no, material_no=order.material_no, part_no=order.part_no, product_name=order.product_name,
            quantity=quantity, receiver='', phone='', address='', requested_ship_date=date.fromisoformat(event['date']),
            remark=f"来源：conservative-v1 模拟批次 {event['id']}；用户明确批准按正式业务补录；未提供收货信息，不代表物流签收，不发邮件",
            status=ShipmentStatus.RECONCILED, matched_order_line_id=order.id,
        )
        db.add(line)
        db.flush()
        order.reconciled_qty += quantity
        order.version += 1
        db.add(LedgerEntry(shipment_line_id=line.id, order_line_id=order.id, entry_type=LedgerType.DEBIT,
                           quantity=quantity, actor_id=actor.id, created_at=now,
                           reason=f"{PROMOTION_TOKEN}：用户批准模拟批次转为正式核销；保留来源，不发送供应商邮件"))
        add_audit_event(db, actor=actor, action='批准批次入账', object_type='ShipmentLine', object_id=str(line.id),
                        dealer_id=order.dealer_id, detail=f"批准来源 {event['id']}，发货日 {event['date']}，数量 {quantity} 桶；不发邮件",
                        before={'remaining_qty': before}, after={'remaining_qty': before - quantity, 'source_event': event['id']})
        line_ids.append(line.id)
    result = dict(already_applied=False, lines=len(line_ids), requests=len(requests), quantity=str(sum(required.values())), line_ids=line_ids)
    db.add(ImportJob(token=PROMOTION_TOKEN, created_by=actor.id, committed_at=now, error_json='[]',
                     payload_json=json.dumps({'source': 'user-approved simulation', 'evidence_sha256': evidence_hash,
                                              'events': approved_events, 'result': result}, ensure_ascii=False)))
    db.flush()
    return result
