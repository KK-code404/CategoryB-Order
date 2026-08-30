from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MaterialMapping, SalesOrderLine, ShipmentLine, ShipmentStatus


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 用可解释的确定性规则完成物料、订单和余额匹配，异常只进入人工队列。
def match_shipment_line(db: Session, line: ShipmentLine) -> ShipmentLine:
    line.matched_order_line_id = None
    line.part_no = None
    line.confidence = None
    mapping = db.scalar(select(MaterialMapping).where(MaterialMapping.material_no == line.material_no))
    if not mapping:
        line.status = ShipmentStatus.EXCEPTION
        line.exception_reason = f"物料号 {line.material_no} 未配置零件映射"
        return line

    line.part_no = mapping.part_no
    candidates = db.scalars(
        select(SalesOrderLine).where(
            SalesOrderLine.dealer_id == line.request.dealer_id,
            SalesOrderLine.order_no == line.order_no,
            SalesOrderLine.part_no == mapping.part_no,
        )
    ).all()
    if not candidates:
        line.status = ShipmentStatus.EXCEPTION
        line.exception_reason = "未找到该代理商、订单号和零件号对应的订单行"
        return line
    if len(candidates) > 1:
        line.status = ShipmentStatus.EXCEPTION
        line.exception_reason = "匹配到多条订单行，需要人工选择"
        return line

    order_line = candidates[0]
    remaining = Decimal(order_line.ordered_qty) - Decimal(order_line.reconciled_qty)
    line.matched_order_line_id = order_line.id
    line.confidence = Decimal("1.0000")
    if Decimal(line.quantity) > remaining:
        line.status = ShipmentStatus.EXCEPTION
        line.exception_reason = f"申请数量 {line.quantity} 超过剩余未发数量 {remaining}"
        return line

    line.status = ShipmentStatus.PENDING
    line.exception_reason = None
    return line

