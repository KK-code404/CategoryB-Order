# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 从真实核销流水生成按月日历台账，保留冲销和未分日历史差额，不伪造物流发货记录。
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from ..models import LedgerEntry, LedgerType, SalesOrderLine, ShipmentLine, ShipmentRequest, User, UserRole
from ..schemas import DailyShipmentReport, DailyShipmentRow


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 限定为合法自然月，避免无限日期列和不明确的跨年统计。
def report_month(value: str | None) -> tuple[str, list[date]]:
    value = value or datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m")
    try:
        start = date.fromisoformat(f"{value}-01")
        if value != start.strftime("%Y-%m") or not 1900 <= start.year <= 2100:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=422, detail="月份须为 YYYY-MM，年份范围为 1900—2100")
    return value, [date(start.year, start.month, day) for day in range(1, monthrange(start.year, start.month)[1] + 1)]


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 用三次批量查询完成权限内汇总，避免逐订单读取流水，并按原申请日期抵减冲销。
def daily_shipments(db: Session, user: User, month: str | None) -> DailyShipmentReport:
    month, dates = report_month(month)
    scope = SalesOrderLine.dealer_id == user.dealer_id if user.role == UserRole.DEALER else True
    orders = db.scalars(select(SalesOrderLine).where(scope).options(joinedload(SalesOrderLine.dealer))
                        .order_by(SalesOrderLine.order_no, SalesOrderLine.dealer_id, SalesOrderLine.part_no)).all()
    signed_qty = case((LedgerEntry.entry_type == LedgerType.DEBIT, LedgerEntry.quantity), else_=-LedgerEntry.quantity)
    source = (select(LedgerEntry.order_line_id, func.sum(signed_qty).label("quantity"))
              .join(SalesOrderLine, LedgerEntry.order_line_id == SalesOrderLine.id)
              .join(ShipmentLine, LedgerEntry.shipment_line_id == ShipmentLine.id)
              .join(ShipmentRequest, ShipmentLine.request_id == ShipmentRequest.id)
              .where(scope, ShipmentRequest.dealer_id == SalesOrderLine.dealer_id))
    all_time = dict(db.execute(source.group_by(LedgerEntry.order_line_id)).all())
    by_day = db.execute(source.add_columns(ShipmentLine.requested_ship_date)
                        .where(ShipmentLine.requested_ship_date.between(dates[0], dates[-1]))
                        .group_by(LedgerEntry.order_line_id, ShipmentLine.requested_ship_date)).all()
    cells: dict[int, dict[str, Decimal]] = {}
    for order_id, quantity, ship_date in by_day:
        cells.setdefault(order_id, {})[ship_date.isoformat()] = Decimal(quantity)
    rows = []
    for order in orders:
        daily = cells.get(order.id, {})
        rows.append(DailyShipmentRow(
            id=order.id, dealer_id=order.dealer_id, dealer_code=order.dealer.code, dealer_name=order.dealer.name,
            order_no=order.order_no, part_no=order.part_no, material_no=order.material_no,
            product_name=order.product_name, unit=order.unit, version=order.version, ordered_qty=order.ordered_qty,
            reconciled_qty=order.reconciled_qty, remaining_qty=order.ordered_qty - order.reconciled_qty,
            undated_qty=order.reconciled_qty - all_time.get(order.id, Decimal(0)),
            month_qty=sum(daily.values(), Decimal(0)), daily=daily,
        ))
    return DailyShipmentReport(month=month, dates=[day.isoformat() for day in dates], rows=rows)
