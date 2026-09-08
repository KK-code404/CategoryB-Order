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

    supplier = Supplier(code="TSUP", name="测试油品供应商", email="supplier-a@example.test")
    dealers = [
        Dealer(code="TDA", name="测试代理商甲", email="dealer-a@example.test"),
        Dealer(code="TDB", name="测试代理商乙", email="dealer-b@example.test"),
        Dealer(code="TDC", name="测试代理商丙", email="dealer-c@example.test"),
    ]
    db.add_all([supplier, *dealers])
    db.flush()

    password = settings.initial_admin_password or "Demo123!"
    db.add_all([
        User(email=settings.initial_admin_email, display_name="系统管理员", password_hash=hash_password(password), role=UserRole.ADMIN),
        User(email="sales@example.test", display_name="测试销售员", password_hash=hash_password("Demo123!"), role=UserRole.SALES),
        User(email="dealer-a@example.test", display_name="测试代理商用户", password_hash=hash_password("Demo123!"), role=UserRole.DEALER, dealer_id=dealers[0].id),
    ])

    mappings = [
        MaterialMapping(material_no="MAT-D01", part_no="PART-D01", product_name="测试柴油机油 A 18L", brand_code="TEST", supplier_id=supplier.id),
        MaterialMapping(material_no="MAT-D02", part_no="PART-D02", product_name="测试柴油机油 B 18L", brand_code="TEST", supplier_id=supplier.id),
        MaterialMapping(material_no="MAT-G01", part_no="PART-G01", product_name="测试燃气机油 A 18L", brand_code="TEST", supplier_id=supplier.id),
        MaterialMapping(material_no="MAT-H01", part_no="PART-H01", product_name="测试液压油 A 18L", brand_code="TEST", supplier_id=supplier.id),
    ]
    db.add_all(mappings)
    db.flush()

    orders = [
        SalesOrderLine(dealer_id=dealers[0].id, order_no="TEST-ORD-001", part_no="PART-D01", material_no="MAT-D01", product_name=mappings[0].product_name, ordered_qty=Decimal("2000"), reconciled_qty=Decimal("450"), unit="桶"),
        SalesOrderLine(dealer_id=dealers[0].id, order_no="TEST-ORD-001", part_no="PART-D02", material_no="MAT-D02", product_name=mappings[1].product_name, ordered_qty=Decimal("2000"), reconciled_qty=Decimal("2000"), unit="桶"),
        SalesOrderLine(dealer_id=dealers[0].id, order_no="TEST-ORD-002", part_no="PART-G01", material_no="MAT-G01", product_name=mappings[2].product_name, ordered_qty=Decimal("400"), reconciled_qty=Decimal("110"), unit="桶"),
        SalesOrderLine(dealer_id=dealers[1].id, order_no="TEST-ORD-003", part_no="PART-H01", material_no="MAT-H01", product_name=mappings[3].product_name, ordered_qty=Decimal("500"), reconciled_qty=Decimal("120"), unit="桶"),
    ]
    db.add_all(orders)
    db.flush()

    now = datetime.now(timezone.utc)
    scenarios = [
        (dealers[0], "TEST-ORD-001", "MAT-D01", Decimal("40"), ShipmentStatus.PENDING, "测试正常申请"),
        (dealers[0], "TEST-ORD-002", "MAT-G01", Decimal("16"), ShipmentStatus.PENDING, "测试正常申请"),
        (dealers[1], "TEST-ORD-003", "MAT-H01", Decimal("20"), ShipmentStatus.PENDING, "测试正常申请"),
        (dealers[0], "TEST-ORD-001", "MAT-D01", Decimal("32"), ShipmentStatus.PENDING, "测试加急申请"),
        (dealers[2], "TEST-ORD-999", "MAT-G01", Decimal("12"), ShipmentStatus.EXCEPTION, "测试异常：订单待补录"),
        (dealers[0], "TEST-ORD-001", "MAT-D02", Decimal("8"), ShipmentStatus.EXCEPTION, "测试异常：余额不足"),
        (dealers[0], "TEST-ORD-002", "MAT-G01", Decimal("20"), ShipmentStatus.PENDING, "测试正常申请"),
    ]
    demo_rows = []
    for cycle in range(4):
        for dealer, order_no, material_no, base_quantity, desired_status, remark in scenarios:
            row_number = len(demo_rows) + 1
            demo_rows.append((
                dealer,
                f"TEST-BATCH-{row_number:02d}",
                order_no,
                material_no,
                base_quantity + Decimal(cycle * 2),
                desired_status,
                f"测试收货地址{row_number:02d}",
                remark,
            ))
    for index, (dealer, batch, order_no, material_no, quantity, desired_status, address, remark) in enumerate(demo_rows, start=1):
        request = ShipmentRequest(request_no=f"TEST-SHIP-{index:04d}", dealer_id=dealer.id, sender_email=dealer.email, subject=f"[测试发货申请] {dealer.code} {batch}", batch_no=batch, message_id=f"<test-{index}@example.test>", imap_uid=str(index), uid_validity="test", attachment_name=f"{batch}.xlsx", attachment_sha256=f"{index:064x}", attachment_path=f"storage/test/{batch}.xlsx", received_at=now - timedelta(minutes=index * 17))
        db.add(request)
        db.flush()
        mapping = next((item for item in mappings if item.material_no == material_no), None)
        line = ShipmentLine(request_id=request.id, row_fingerprint=f"{index + 100:064x}", order_no=order_no, material_no=material_no, product_name=mapping.product_name if mapping else "测试待匹配产品", quantity=quantity, receiver=f"测试收货人{index:02d}", phone=f"000-0000-{index:04d}", address=address, requested_ship_date=date.today() + timedelta(days=(index % 10) + 1), remark=remark, status=ShipmentStatus.PENDING)
        line.request = request
        db.add(line)
        match_shipment_line(db, line)
        if desired_status == ShipmentStatus.EXCEPTION and line.status == ShipmentStatus.PENDING:
            line.status = ShipmentStatus.EXCEPTION
            line.exception_reason = "测试异常：需要人工核对订单信息"

    db.add_all([
        AuditEvent(actor_name="测试系统", action="邮件抓取", object_type="ShipmentRequest", object_id="TEST-SHIP-0001", detail="生成 28 条测试发货明细", result="成功", dealer_id=dealers[0].id, ip_address="system"),
        AuditEvent(actor_name="测试销售员", action="核销", object_type="ShipmentLine", object_id="测试记录", detail="核销测试物料 MAT-G01 数量 50，核销后余额 290", result="成功", dealer_id=dealers[0].id, ip_address="127.0.0.1"),
        AuditEvent(actor_name="测试审核员", action="退回修改", object_type="ShipmentLine", object_id="测试记录", detail="数量超过剩余未发数量，已退回测试代理商修改", result="已退回", dealer_id=dealers[0].id, ip_address="127.0.0.1"),
    ])
    db.commit()

