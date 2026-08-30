from __future__ import annotations

import email
import hashlib
import imaplib
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Dealer, ShipmentLine, ShipmentRequest, ShipmentStatus
from .audit import add_audit_event
from .excel_import import parse_shipment_workbook
from .matching import match_shipment_line

SUBJECT_PATTERN = re.compile(r"^\[发货申请\]\s+(?P<dealer>\S+)\s+(?P<batch>\S+)$")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 解码不同邮件客户端生成的主题编码，确保标准主题能够稳定匹配。
def _decode_subject(message: Message) -> str:
    return str(make_header(decode_header(message.get("Subject", "")))).strip()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 兼容 Excel 日期值与标准日期文本，并拒绝无法解释的发货日期。
def _parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("要求发货日期格式应为 YYYY-MM-DD")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将单封标准邮件及附件幂等入库，并逐行执行确定性匹配。
def ingest_message_bytes(db: Session, raw_message: bytes, imap_uid: str, uid_validity: str = "") -> int:
    message = email.message_from_bytes(raw_message)
    subject = _decode_subject(message)
    match = SUBJECT_PATTERN.match(subject)
    if not match:
        raise ValueError("邮件主题必须为：[发货申请] 代理商编码 批次号")

    sender = parseaddr(message.get("From", ""))[1].lower()
    dealer = db.scalar(select(Dealer).where(Dealer.code == match.group("dealer"), Dealer.email == sender, Dealer.active.is_(True)))
    if not dealer:
        raise ValueError("发件邮箱与代理商编码不匹配")

    attachments: list[tuple[str, bytes]] = []
    for part in message.walk():
        filename = part.get_filename()
        if filename and filename.lower().endswith(".xlsx"):
            attachments.append((str(make_header(decode_header(filename))), part.get_payload(decode=True) or b""))
    if len(attachments) != 1:
        raise ValueError("每封申请邮件必须且只能包含一个 .xlsx 附件")

    filename, content = attachments[0]
    digest = hashlib.sha256(content).hexdigest()
    message_id = message.get("Message-ID", "").strip() or f"uid:{uid_validity}:{imap_uid}"
    existing = db.scalar(select(ShipmentRequest).where(ShipmentRequest.message_id == message_id, ShipmentRequest.attachment_sha256 == digest))
    if existing:
        return existing.id

    storage_dir = Path(settings.storage_path) / "attachments" / datetime.now(timezone.utc).strftime("%Y/%m/%d")
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_file = storage_dir / f"{digest}.xlsx"
    storage_file.write_bytes(content)

    parsed_rows = parse_shipment_workbook(content, filename)
    request_no = f"SHIP-{datetime.now(timezone.utc):%Y%m%d}-{match.group('batch')}"
    shipment_request = ShipmentRequest(
        request_no=request_no,
        dealer_id=dealer.id,
        sender_email=sender,
        subject=subject,
        batch_no=match.group("batch"),
        message_id=message_id,
        imap_uid=imap_uid,
        uid_validity=uid_validity,
        attachment_name=filename,
        attachment_sha256=digest,
        attachment_path=str(storage_file),
    )
    db.add(shipment_request)
    db.flush()

    for item in parsed_rows:
        row_fingerprint = hashlib.sha256(f"{message_id}|{digest}|{item['_row']}".encode()).hexdigest()
        try:
            quantity = Decimal(str(item["数量"]))
            if quantity <= 0:
                raise ValueError("数量必须大于 0")
            requested_date = _parse_date(item["要求发货日期"])
            critical = [item["订单号"], item["物料号"], item["收货人"], item["联系电话"], item["收货地址"]]
            if not all(str(value or "").strip() for value in critical):
                raise ValueError("订单号、物料号及收货信息不能为空")
            parse_error = None
        except (InvalidOperation, ValueError, TypeError) as exc:
            quantity = Decimal("0")
            requested_date = date.today()
            parse_error = str(exc)

        line = ShipmentLine(
            request_id=shipment_request.id,
            row_fingerprint=row_fingerprint,
            order_no=str(item.get("订单号") or "").strip(),
            material_no=str(item.get("物料号") or "").strip(),
            product_name=str(item.get("品名") or "").strip(),
            quantity=quantity,
            receiver=str(item.get("收货人") or "").strip(),
            phone=str(item.get("联系电话") or "").strip(),
            address=str(item.get("收货地址") or "").strip(),
            requested_ship_date=requested_date,
            remark=str(item.get("备注") or "").strip(),
            status=ShipmentStatus.EXCEPTION if parse_error else ShipmentStatus.PENDING,
            exception_reason=parse_error,
        )
        line.request = shipment_request
        db.add(line)
        if not parse_error:
            match_shipment_line(db, line)

    add_audit_event(db, actor=None, action="邮件抓取", object_type="ShipmentRequest", object_id=request_no, detail=f"接收并解析 {len(parsed_rows)} 条发货明细", dealer_id=dealer.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.scalar(select(ShipmentRequest).where(ShipmentRequest.message_id == message_id, ShipmentRequest.attachment_sha256 == digest))
        if duplicate:
            return duplicate.id
        raise
    return shipment_request.id


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 每分钟读取专用 IMAP 邮箱未处理邮件，成功入库后才标记为已读。
def poll_imap_once() -> int:
    if not settings.imap_host or not settings.imap_username or not settings.imap_password:
        return 0
    processed = 0
    with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port) as client:
        client.login(settings.imap_username, settings.imap_password)
        client.select(settings.imap_folder)
        status, validity = client.response("UIDVALIDITY")
        uid_validity = validity[0].decode() if status == "OK" and validity else ""
        status, data = client.uid("search", None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("IMAP 搜索未读邮件失败")
        for uid_bytes in data[0].split():
            uid = uid_bytes.decode()
            fetch_status, payload = client.uid("fetch", uid, "(RFC822)")
            if fetch_status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            with SessionLocal() as db:
                ingest_message_bytes(db, payload[0][1], uid, uid_validity)
            client.uid("store", uid, "+FLAGS", "(\\Seen)")
            processed += 1
    return processed

