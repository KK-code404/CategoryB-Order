from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import AuditEvent, Dealer, MaterialMapping, SalesOrderLine, ShipmentLine, ShipmentRequest, ShipmentStatus, Supplier, User, UserRole
from .security import hash_password
from .services.matching import match_shipment_line


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 创建首个管理员或可选演示数据，使空数据库具备登录和端到端验收入口。
def seed_database(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return
    if not settings.initial_admin_password and not settings.seed_demo_data:
        return

    supplier = Supplier(code="DFL", name="东风油品供应商", email="supplier@example.com")
    dealers = [
        Dealer(code="JNTQ", name="济南天桥区蓝翔客户", email="north@dealer.com"),
        Dealer(code="DLHL", name="大连鸿路经贸", email="dalian@dealer.com"),
        Dealer(code="QDHD", name="青岛宏运汽配", email="qingdao@dealer.com"),
    ]
    db.add_all([supplier, *dealers])
    db.flush()

    password = settings.initial_admin_password or "Demo123!"
    db.add_all([
        User(email=settings.initial_admin_email, display_name="系统管理员", password_hash=hash_password(password), role=UserRole.ADMIN),
        User(email="sales@example.com", display_name="张伟", password_hash=hash_password("Demo123!"), role=UserRole.SALES),
        User(email="north@dealer.com", display_name="济南代理商", password_hash=hash_password("Demo123!"), role=UserRole.DEALER, dealer_id=dealers[0].id),
    ])

    mappings = [
        MaterialMapping(material_no="TK10018X", part_no="TK10018", product_name="红旋风国六发动机专用油 CK-4 10W-30 18L", brand_code="DFL", supplier_id=supplier.id),
        MaterialMapping(material_no="TK61018X", part_no="TK61018", product_name="红旋风国六发动机专用油 CK-4 10W-30 18L", brand_code="DFL", supplier_id=supplier.id),
        MaterialMapping(material_no="CG60618X", part_no="CG60618", product_name="红旋风天然气发动机专用油 CES 20092 10W-40 18L", brand_code="DFL", supplier_id=supplier.id),
        MaterialMapping(material_no="TK31518X", part_no="TK31518", product_name="红旋风高性能柴油机油 18L", brand_code="DFL", supplier_id=supplier.id),
    ]
    db.add_all(mappings)
    db.flush()

    orders = [
        SalesOrderLine(dealer_id=dealers[0].id, order_no="200017736", part_no="TK10018", material_no="TK10018X", product_name=mappings[0].product_name, ordered_qty=Decimal("2000"), reconciled_qty=Decimal("450"), unit="桶"),
        SalesOrderLine(dealer_id=dealers[0].id, order_no="200017736", part_no="TK61018", material_no="TK61018X", product_name=mappings[1].product_name, ordered_qty=Decimal("2000"), reconciled_qty=Decimal("2000"), unit="桶"),
        SalesOrderLine(dealer_id=dealers[0].id, order_no="200018391", part_no="CG60618", material_no="CG60618X", product_name=mappings[2].product_name, ordered_qty=Decimal("400"), reconciled_qty=Decimal("110"), unit="桶"),
        SalesOrderLine(dealer_id=dealers[1].id, order_no="200018464", part_no="TK31518", material_no="TK31518X", product_name=mappings[3].product_name, ordered_qty=Decimal("500"), reconciled_qty=Decimal("120"), unit="桶"),
    ]
    db.add_all(orders)
    db.flush()

    now = datetime.now(timezone.utc)
    demo_rows = [
        (dealers[0], "BATCH-0826-A", "200017736", "TK10018X", Decimal("40"), ShipmentStatus.PENDING, "济南市天桥区蓝翔路店", "8月26日"),
        (dealers[0], "BATCH-0826-B", "200018391", "CG60618X", Decimal("60"), ShipmentStatus.PENDING, "沈阳市和平区物流园", "终端客户急需"),
        (dealers[0], "BATCH-0827-A", "200017736", "TK61018X", Decimal("20"), ShipmentStatus.EXCEPTION, "济南市历城区工业园", "余额不足"),
        (dealers[1], "BATCH-0827-B", "200018464", "TK31518X", Decimal("30"), ShipmentStatus.PENDING, "大连市甘井子区华北路", "下午送达"),
        (dealers[2], "BATCH-0828-A", "200019999", "CG60618X", Decimal("56"), ShipmentStatus.EXCEPTION, "青岛市城阳区物流中心", "订单待补录"),
    ]
    for index, (dealer, batch, order_no, material_no, quantity, desired_status, address, remark) in enumerate(demo_rows, start=1):
        request = ShipmentRequest(request_no=f"SHIP-20260830-{index:04d}", dealer_id=dealer.id, sender_email=dealer.email, subject=f"[发货申请] {dealer.code} {batch}", batch_no=batch, message_id=f"<demo-{index}@local>", imap_uid=str(index), uid_validity="demo", attachment_name=f"{batch}.xlsx", attachment_sha256=f"{index:064x}", attachment_path=f"storage/demo/{batch}.xlsx", received_at=now - timedelta(minutes=index * 17))
        db.add(request)
        db.flush()
        mapping = next((item for item in mappings if item.material_no == material_no), None)
        line = ShipmentLine(request_id=request.id, row_fingerprint=f"{index + 100:064x}", order_no=order_no, material_no=material_no, product_name=mapping.product_name if mapping else "待匹配产品", quantity=quantity, receiver="杨冬雪", phone="15940217200", address=address, requested_ship_date=date.today() + timedelta(days=index), remark=remark, status=ShipmentStatus.PENDING)
        line.request = request
        db.add(line)
        match_shipment_line(db, line)
        if desired_status == ShipmentStatus.EXCEPTION and line.status == ShipmentStatus.PENDING:
            line.status = ShipmentStatus.EXCEPTION
            line.exception_reason = "演示异常：需要人工核对订单信息"

    db.add_all([
        AuditEvent(actor_name="系统", action="邮件抓取", object_type="ShipmentRequest", object_id="SHIP-20260830-0001", detail="接收并解析 1 条发货明细", result="成功", dealer_id=dealers[0].id, ip_address="system"),
        AuditEvent(actor_name="张伟", action="核销", object_type="ShipmentLine", object_id="历史记录", detail="核销物料 CG60618X 数量 50，核销后余额 290", result="成功", dealer_id=dealers[0].id, ip_address="127.0.0.1"),
        AuditEvent(actor_name="李娜", action="退回修改", object_type="ShipmentLine", object_id="历史记录", detail="数量超过剩余未发数量，已退回代理商修改", result="已退回", dealer_id=dealers[0].id, ip_address="127.0.0.1"),
    ])
    db.commit()

