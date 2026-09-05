"""Read-only charts and a reproducible, isolated historical demonstration.

Simulation never creates requests, ledger entries or outbound mail. Its opening
balances come from the committed import snapshot, not today's mutable balances.
"""
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from statistics import median

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from ..models import ImportJob, LedgerEntry, LedgerType, SalesOrderLine, ShipmentLine, ShipmentRequest, User, UserRole

CUTOFF = date(2026, 8, 26)
SIM_END = date(2026, 9, 3)
IMPORT_TOKEN = "5a6fa68cf8fc63fd9a9d86b033c890012bab040b8dcb1027"
PROMOTION_TOKEN = "approved-20260827-20260903-v1"
EXCLUDED_ORDERS = {"200018171"}
ZERO = Decimal(0)


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def amount(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def identity(order: SalesOrderLine) -> str:
    return f"{order.dealer.code}|{order.order_no.strip()}|{order.part_no}"


def simulate_history(snapshot: list[dict], history: dict, visible_keys: set[str]) -> list[dict]:
    """Conservative scenario v1: six weekdays, three dispatch days per dealer.

    Group by unit, never pool unlike quantities. Up to two lines per dispatch;
    at most 15% of each line's opening remainder and 40 units per dispatch.
    Whole-period budget <=8% of remainder and <=45% of recent 28-day volume.
    Inactive dealers get <=1% of remainder, <=40 units (assumed small restart).
    """
    groups = defaultdict(list)
    for row in snapshot:
        if row["key"] in visible_keys and row["order_no"].strip() not in EXCLUDED_ORDERS:
            groups[(row["dealer"], row["unit"])].append(row)
    weekdays = [d for d in days_between(CUTOFF + timedelta(days=1), SIM_END) if d.weekday() < 5]
    events = []
    for (dealer, unit), rows in sorted(groups.items()):
        remaining = {r["key"]: Decimal(str(r["remaining_qty"])) for r in rows}
        opening = sum(remaining.values(), ZERO)
        recent = sum((q for r in rows for d, q in history.get(r["key"], {}).items()
                      if CUTOFF - timedelta(days=27) <= d <= CUTOFF and q > 0), ZERO)
        budget = min(opening * Decimal("0.08"), recent * Decimal("0.45")) if recent else min(opening * Decimal("0.01"), Decimal(40))
        budget = budget.quantize(Decimal(1), rounding=ROUND_DOWN)
        counts = defaultdict(int)
        offset = int(hashlib.sha256(dealer.encode()).hexdigest()[:8], 16) % 2
        for day in weekdays[offset::2]:
            def priority(row):
                last = max(history.get(row["key"], {}), default=date.min)
                tie = hashlib.sha256(f"scenario-v1|{day}|{row['key']}".encode()).hexdigest()
                return (counts[row["key"]], -last.toordinal(), tie)
            eligible = sorted((r for r in rows if remaining[r["key"]] >= 1 and counts[r["key"]] < 2), key=priority)
            for row in eligible[:2]:
                key = row["key"]
                samples = [q for d, q in history.get(key, {}).items() if q > 0 and d <= CUTOFF]
                typical = Decimal(median(samples)) * Decimal("0.5") if samples else Decimal(10)
                qty = min(budget, remaining[key], Decimal(str(row["remaining_qty"])) * Decimal("0.15"), typical, Decimal(40))
                qty = qty.quantize(Decimal(1), rounding=ROUND_DOWN)
                if qty <= 0:
                    continue
                events.append({"id": f"SIM-{day:%Y%m%d}-{hashlib.sha256(key.encode()).hexdigest()[:10]}",
                               "key": key, "date": day.isoformat(), "quantity": amount(qty), "simulated": True})
                budget -= qty
                remaining[key] -= qty
                counts[key] += 1
    return sorted(events, key=lambda e: (e["date"], e["key"]))


def reconciliation_analytics(db: Session, user: User, start: date, end: date) -> dict:
    if start > end or (end - start).days > 61 or start.year < 1900 or end.year > 2100:
        raise HTTPException(422, "请选择顺序正确且不超过 62 天的日期范围（1900—2100 年）")
    scope = SalesOrderLine.dealer_id == user.dealer_id if user.role == UserRole.DEALER else True
    orders = db.scalars(select(SalesOrderLine).where(scope).options(joinedload(SalesOrderLine.dealer))
                        .order_by(SalesOrderLine.dealer_id, SalesOrderLine.order_no, SalesOrderLine.part_no)).all()
    signed = case((LedgerEntry.entry_type == LedgerType.DEBIT, LedgerEntry.quantity), else_=-LedgerEntry.quantity)
    query = (select(LedgerEntry.order_line_id, ShipmentLine.requested_ship_date, func.sum(signed))
             .join(SalesOrderLine, LedgerEntry.order_line_id == SalesOrderLine.id)
             .join(ShipmentLine, LedgerEntry.shipment_line_id == ShipmentLine.id)
             .join(ShipmentRequest, ShipmentLine.request_id == ShipmentRequest.id)
             .where(scope, ShipmentRequest.dealer_id == SalesOrderLine.dealer_id)
             .group_by(LedgerEntry.order_line_id, ShipmentLine.requested_ship_date))
    daily = defaultdict(dict)
    for order_id, day, quantity in db.execute(query):
        daily[order_id][day] = Decimal(quantity)

    def row_data(order, ordered, opening, closing, cells, undated=ZERO):
        return dict(id=order.id, dealer_id=order.dealer_id, dealer_code=order.dealer.code,
                    dealer_name=order.dealer.name, order_no=order.order_no, part_no=order.part_no,
                    unit=order.unit, ordered_qty=amount(ordered), opening_qty=amount(opening),
                    closing_qty=amount(closing), undated_qty=amount(undated),
                    daily={d.isoformat(): amount(q) for d, q in cells.items() if start <= d <= end})

    actual_rows = []
    for order in orders:
        current = order.ordered_qty - order.reconciled_qty
        opening = current + sum((q for d, q in daily[order.id].items() if d >= start), ZERO)
        closing = current + sum((q for d, q in daily[order.id].items() if d > end), ZERO)
        undated = order.reconciled_qty - sum(daily[order.id].values(), ZERO)
        actual_rows.append(row_data(order, order.ordered_qty, opening, closing, daily[order.id], undated))

    promoted = db.scalar(select(ImportJob.committed_at).where(ImportJob.token == PROMOTION_TOKEN))
    if promoted:
        # Retire the scenario once approved: legacy clients cannot count it again.
        return dict(start=start.isoformat(), end=end.isoformat(), dates=[d.isoformat() for d in days_between(start, end)],
                    generated_at=datetime.now(timezone.utc).isoformat(), actual=actual_rows,
                    simulation=dict(available=False, imported=True, cutoff=CUTOFF.isoformat(), start="2026-08-27",
                                    end=SIM_END.isoformat(), version="conservative-v1", rows=[], events=[],
                                    reason="这批数据已获用户确认并纳入正式核销，请查看正式台账"))

    job = db.scalar(select(ImportJob).where(ImportJob.token == IMPORT_TOKEN, ImportJob.committed_at.is_not(None)))
    snapshot = json.loads(job.payload_json) if job else []
    visible = {identity(o): o for o in orders}
    # Confirmed unit corrections apply to both views; quantities stay frozen.
    snapshot = [{**r, "unit": visible[r["key"]].unit} if r["key"] in visible else r for r in snapshot]
    # Only the original manual-import DEBITs inform the historical scenario.
    # Later corrections remain in the real view, not in this frozen scenario.
    historical = defaultdict(dict)
    imported = (select(LedgerEntry.order_line_id, ShipmentLine.requested_ship_date, func.sum(LedgerEntry.quantity))
                .join(SalesOrderLine, LedgerEntry.order_line_id == SalesOrderLine.id)
                .join(ShipmentLine, LedgerEntry.shipment_line_id == ShipmentLine.id)
                .join(ShipmentRequest, ShipmentLine.request_id == ShipmentRequest.id)
                .where(scope, ShipmentRequest.dealer_id == SalesOrderLine.dealer_id,
                       ShipmentRequest.uid_validity == "manual-history", LedgerEntry.entry_type == LedgerType.DEBIT,
                       LedgerEntry.reason.contains("real-data-20260903"), ShipmentLine.requested_ship_date <= CUTOFF)
                .group_by(LedgerEntry.order_line_id, ShipmentLine.requested_ship_date))
    by_id = {o.id: identity(o) for o in orders}
    for order_id, day, quantity in db.execute(imported):
        historical[by_id[order_id]][day] = Decimal(quantity)
    events = simulate_history(snapshot, historical, set(visible))
    simulated = defaultdict(dict)
    for event in events:
        simulated[event["key"]][date.fromisoformat(event["date"])] = Decimal(event["quantity"])
    scenario_rows = []
    for record in snapshot:
        key = record["key"]
        if key not in visible or record["order_no"].strip() in EXCLUDED_ORDERS:
            continue
        order = visible[key]
        cells = {**historical[key], **simulated[key]}
        final = Decimal(str(record["remaining_qty"])) - sum(simulated[key].values(), ZERO)
        opening = final + sum((q for d, q in cells.items() if d >= start), ZERO)
        closing = final + sum((q for d, q in cells.items() if d > end), ZERO)
        row = row_data(order, Decimal(str(record["ordered_qty"])), opening, closing, cells)
        row["unit"] = record["unit"]
        row["baseline_remaining_qty"] = amount(Decimal(str(record["remaining_qty"])))
        scenario_rows.append(row)
    return dict(start=start.isoformat(), end=end.isoformat(), dates=[d.isoformat() for d in days_between(start, end)],
                generated_at=datetime.now(timezone.utc).isoformat(), actual=actual_rows,
                simulation=dict(available=bool(scenario_rows), cutoff=CUTOFF.isoformat(), start="2026-08-27", end=SIM_END.isoformat(),
                                version="conservative-v1", rows=scenario_rows,
                                events=[dict(id=e["id"], order_line_id=visible[e["key"]].id, date=e["date"], quantity=e["quantity"], simulated=True) for e in events],
                                reason="" if scenario_rows else "当前账号没有本次历史导入的订单，无法生成这批模拟数据"))
