import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ImportJob, LedgerEntry, OutboundMail, SalesOrderLine, ShipmentLine, ShipmentRequest
from app.services.reconciliation_analytics import IMPORT_TOKEN, simulate_history

URL = "/api/orders/reconciliation-analytics?start=2026-08-27&end=2026-09-03"


def install_snapshot():
    with SessionLocal() as db:
        orders = db.scalars(select(SalesOrderLine)).all()
        snapshot = [dict(key=f"{o.dealer.code}|{o.order_no}|{o.part_no}", dealer=o.dealer.code,
                         order_no=o.order_no, part_no=o.part_no, unit=o.unit,
                         ordered_qty=str(o.ordered_qty), remaining_qty=str(o.ordered_qty-o.reconciled_qty)) for o in orders]
        db.add(ImportJob(token=IMPORT_TOKEN, payload_json=json.dumps(snapshot), error_json="[]", created_by=1,
                         committed_at=datetime.now(timezone.utc)))
        db.commit()


def fingerprint():
    with SessionLocal() as db:
        return ([tuple(getattr(o, c.name) for c in SalesOrderLine.__table__.columns) for o in db.scalars(select(SalesOrderLine)).all()],
                [db.scalar(select(func.count()).select_from(m)) for m in (LedgerEntry, ShipmentLine, ShipmentRequest, OutboundMail)])


def test_read_only_deterministic_and_unit_scoped(sales_client):
    install_snapshot()
    before = fingerprint()
    first = sales_client.get(URL).json()
    second = sales_client.get(URL).json()
    assert first["simulation"]["available"]
    assert first["simulation"] == second["simulation"]
    assert before == fingerprint()
    assert len(first["dates"]) == 8
    assert first["simulation"]["events"]
    for event in first["simulation"]["events"]:
        assert event["simulated"] is True
        assert date.fromisoformat(event["date"]).weekday() < 5
        row = next(r for r in first["simulation"]["rows"] if r["id"] == event["order_line_id"])
        assert 0 < Decimal(event["quantity"]) <= Decimal(row["baseline_remaining_qty"]) * Decimal(".15")
        assert Decimal(event["quantity"]) <= 40
    for row in first["simulation"]["rows"]:
        total = sum(map(Decimal, row["daily"].values()))
        assert Decimal(row["opening_qty"]) - total == Decimal(row["closing_qty"])
        assert Decimal(row["closing_qty"]) >= 0
        assert not any(key in row for key in ("phone", "address", "email", "receiver"))


def test_authorization_and_missing_snapshot(client):
    assert client.get(URL).status_code == 401
    client.post("/api/auth/login", json={"email": "north@dealer.com", "password": "Demo123!"})
    assert client.get(URL).json()["simulation"]["available"] is False
    install_snapshot()
    report = client.get(URL + "&dealer_id=2").json()
    assert all(r["dealer_id"] == 1 for r in report["actual"] + report["simulation"]["rows"])
    assert all(e["order_line_id"] in {r["id"] for r in report["simulation"]["rows"]} for e in report["simulation"]["events"])


def test_ledger_reversal_and_cross_period_opening(sales_client):
    with SessionLocal() as db:
        line = db.get(ShipmentLine, 1)
        line.requested_ship_date = date(2026, 8, 28)
        order_id = line.matched_order_line_id
        db.commit()
    before = next(r for r in sales_client.get(URL).json()["actual"] if r["id"] == order_id)
    assert sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [1]}).status_code == 200
    row = next(r for r in sales_client.get(URL).json()["actual"] if r["id"] == order_id)
    assert Decimal(row["daily"]["2026-08-28"]) == 40
    assert row["opening_qty"] == before["opening_qty"]
    assert Decimal(row["opening_qty"]) - Decimal(row["closing_qty"]) == 40
    sub = sales_client.get("/api/orders/reconciliation-analytics?start=2026-09-01&end=2026-09-03").json()
    assert next(r for r in sub["actual"] if r["id"] == order_id)["opening_qty"] == row["closing_qty"]
    assert sales_client.post("/api/shipment-lines/1/reverse", json={"reason": "测试客户取消"}).status_code == 200
    reversed_row = next(r for r in sales_client.get(URL).json()["actual"] if r["id"] == order_id)
    assert Decimal(reversed_row["daily"]["2026-08-28"]) == 0
    assert reversed_row["closing_qty"] == before["closing_qty"]


def test_snapshot_not_changed_by_real_business(sales_client):
    install_snapshot()
    first = sales_client.get(URL).json()
    assert sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [1]}).status_code == 200
    second = sales_client.get(URL).json()
    assert first["simulation"] == second["simulation"]


@pytest.mark.parametrize("query", ["start=2026-09-04&end=2026-09-03", "start=2026-01-01&end=2026-09-03", "start=invalid&end=2026-09-03", "start=1800-01-01&end=1800-01-02"])
def test_invalid_range(sales_client, query):
    assert sales_client.get("/api/orders/reconciliation-analytics?" + query).status_code == 422


def test_simulator_limits_exclusion_and_filter_stability():
    rows = [dict(key=f"A|{i}|P", dealer="A", unit="桶", order_no=str(i), remaining_qty="100", ordered_qty="100") for i in range(10)]
    rows += [dict(key="A|200018171|P", dealer="A", unit="桶", order_no="200018171 ", remaining_qty="10000", ordered_qty="10000")]
    rows += [dict(key="A|zero|P", dealer="A", unit="桶", order_no="zero", remaining_qty="0", ordered_qty="100")]
    history = {r["key"]: {date(2026, 8, 24): Decimal(10)} for r in rows[:10]}
    keys = {r["key"] for r in rows}
    events = simulate_history(rows, history, keys)
    assert sum(Decimal(e["quantity"]) for e in events) <= 45
    assert all("200018171" not in e["key"] and "zero" not in e["key"] for e in events)
    assert len(events) <= 6
    assert events == simulate_history(list(reversed(rows)), history, keys)
