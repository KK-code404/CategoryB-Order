from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.db import SessionLocal
from app.models import ShipmentRequest
from app.services.excel_import import parse_shipment_workbook
from app.services.mail_ingest import ingest_message_bytes


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 生成符合标准模板的内存附件，避免测试依赖外部文件。
def _shipment_xlsx(formula: bool = False) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "发货申请"
    sheet.append(["订单号", "物料号", "品名", "数量", "收货人", "联系电话", "收货地址", "要求发货日期", "备注"])
    sheet.append(["200017736", "TK10018X", "红旋风机油", "=20+20" if formula else 40, "杨冬雪", "15940217200", "济南市天桥区工业园", "2026-09-01", "终端客户需求"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 组装完整 RFC822 邮件以验证主题、发件人、附件和幂等链路。
def _message_bytes(content: bytes) -> bytes:
    message = EmailMessage()
    message["From"] = "north@dealer.com"
    message["To"] = "shipments@example.com"
    message["Subject"] = "[发货申请] JNTQ BATCH-TEST-001"
    message["Message-ID"] = "<batch-test-001@example.com>"
    message.set_content("请按附件安排发货。")
    message.add_attachment(content, maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="发货申请.xlsx")
    return message.as_bytes()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证同一 Message-ID 与附件哈希只会生成一份申请记录。
def test_mail_ingest_is_idempotent(client):
    raw = _message_bytes(_shipment_xlsx())
    with SessionLocal() as db:
        first = ingest_message_bytes(db, raw, "9001", "77")
    with SessionLocal() as db:
        second = ingest_message_bytes(db, raw, "9001", "77")
        assert first == second
        assert db.query(ShipmentRequest).filter(ShipmentRequest.message_id == "<batch-test-001@example.com>").count() == 1


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证带公式附件在进入业务解析前被拒绝。
def test_formula_is_rejected(client):
    with pytest.raises(ValueError, match="不能包含公式"):
        parse_shipment_workbook(_shipment_xlsx(formula=True), "发货申请.xlsx")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 直接读取平台分发模板，验证模板文件与后端解析契约保持一致。
def test_distributed_shipment_template_is_parseable(client):
    template = BytesIO((Path(__file__).parents[2] / 'frontend' / 'public' / 'templates' / '发货申请标准模板.xlsx').read_bytes())
    rows = parse_shipment_workbook(template.getvalue(), "发货申请标准模板.xlsx")
    assert rows[0]["订单号"] == "200017736"
    assert rows[0]["物料号"] == "TK10018X"
