# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 用隔离订单验证日历汇总、冲销、日期边界与代理商隔离，不修改运行中的演示数据库。
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import SalesOrderLine, ShipmentLine


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 建立同日多批次申请，确保汇总不是取最后一笔或使用邮件接收日期。
def dated_lines():
    with SessionLocal() as db:
        original = db.get(ShipmentLine, 1)
        original.requested_ship_date = date(2026, 2, 3)
        values = {column.name: getattr(original, column.name) for column in ShipmentLine.__table__.columns
                  if column.name not in {"id", "row_fingerprint"}}
        values["quantity"] = Decimal("2.50")
        second = ShipmentLine(**values, row_fingerprint="f" * 64)
        db.add(second)
        db.commit()
        return original.id, second.id


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 验证未核销不入账、十进制累加以及冲销回退原日期，历史数量不分配到任意日期。
def test_daily_aggregation_and_reversal(sales_client):
    first, second = dated_lines()
    url = "/api/orders/daily-shipments?month=2026-02"
    before = sales_client.get(url).json()
    assert len(before["dates"]) == 28
    assert all(row["daily"] == {} for row in before["rows"])
    assert sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [first, second]}).status_code == 200
    report = sales_client.get(url).json()
    row = next(row for row in report["rows"] if row["part_no"] == "TK10018")
    assert Decimal(row["daily"]["2026-02-03"]) == Decimal("42.50")
    assert Decimal(row["month_qty"]) == Decimal("42.50")
    assert Decimal(row["remaining_qty"]) == Decimal("1507.50")
    assert Decimal(row["undated_qty"]) == Decimal("450")
    assert sales_client.post(f"/api/shipment-lines/{first}/reverse", json={"reason": "客户取消发货"}).status_code == 200
    row = next(row for row in sales_client.get(url).json()["rows"] if row["part_no"] == "TK10018")
    assert Decimal(row["daily"]["2026-02-03"]) == Decimal("2.50")
    assert Decimal(row["remaining_qty"]) == Decimal("1547.50")
    assert Decimal(row["undated_qty"]) == Decimal("450")
    assert "receiver" not in row and "phone" not in row and "address" not in row


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 验证月份切换不会重算全期余额，闰日列和跨月发货各归属正确月份。
def test_month_boundaries(sales_client):
    first, second = dated_lines()
    with SessionLocal() as db:
        db.get(ShipmentLine, second).requested_ship_date = date(2026, 3, 1)
        db.commit()
    sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [first, second]})
    feb = next(r for r in sales_client.get("/api/orders/daily-shipments?month=2026-02").json()["rows"] if r["part_no"] == "TK10018")
    mar = next(r for r in sales_client.get("/api/orders/daily-shipments?month=2026-03").json()["rows"] if r["part_no"] == "TK10018")
    assert Decimal(feb["month_qty"]) == 40
    assert Decimal(mar["month_qty"]) == Decimal("2.5")
    assert feb["remaining_qty"] == mar["remaining_qty"]
    assert len(sales_client.get("/api/orders/daily-shipments?month=2024-02").json()["dates"]) == 29


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 同订单号的不同代理商仍按订单行主键隔离，防止通过参数读取其他客户台账。
def test_dealer_scope(client):
    assert client.get("/api/orders/daily-shipments").status_code == 401
    with SessionLocal() as db:
        foreign = db.scalar(select(SalesOrderLine).where(SalesOrderLine.dealer_id == 2))
        foreign.order_no = "200017736"
        db.commit()
    client.post("/api/auth/login", json={"email": "north@dealer.com", "password": "Demo123!"})
    report = client.get("/api/orders/daily-shipments?month=2026-02&dealer_id=2").json()
    assert len(report["rows"]) == 3
    assert all(row["dealer_id"] == 1 for row in report["rows"])


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 非法月份返回明确校验错误，不触发服务器异常。
@pytest.mark.parametrize("month", ["2026-13", "2026-2", "abc", "2200-01"])
def test_invalid_month(sales_client, month):
    assert sales_client.get(f"/api/orders/daily-shipments?month={month}").status_code == 422
