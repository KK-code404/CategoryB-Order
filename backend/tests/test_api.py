from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from app.db import SessionLocal
from app.models import LedgerEntry, OutboundMail, User
from app.security import hash_password


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证登录、工作台内容与安全 Cookie 会话主路径。
def test_login_and_dashboard(sales_client: TestClient):
    response = sales_client.get("/api/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["pending_emails"] >= 1
    assert payload["lines"]
    assert "access_token" in sales_client.cookies


# CHANGE [2026-08-30 18:05 +08:00] [WH400]: 验证管理员可使用非邮箱格式账号登录。
def test_plain_account_login(client: TestClient):
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert admin is not None
        admin.email = "adminkk"
        admin.password_hash = hash_password("test-admin-password-2026!")
        db.commit()
    response = client.post("/api/auth/login", json={"email": "adminkk", "password": "test-admin-password-2026!"})
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证代理商只能读取自己的订单与发货记录。
def test_dealer_data_isolation(client: TestClient):
    login = client.post("/api/auth/login", json={"email": "north@dealer.com", "password": "Demo123!"})
    assert login.status_code == 200
    orders = client.get("/api/orders").json()
    lines = client.get("/api/shipment-lines").json()
    assert orders and all(item["dealer_name"] == "济南天桥区蓝翔客户" for item in orders)
    assert lines and all(item["dealer_name"] == "济南天桥区蓝翔客户" for item in lines)
    assert client.post("/api/shipment-lines/confirm", json={"line_ids": [lines[0]["id"]]}).status_code == 403


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证核销扣减、重复确认拦截、外发箱创建及冲销恢复完整闭环。
def test_confirm_and_reverse_flow(sales_client: TestClient):
    dashboard = sales_client.get("/api/dashboard").json()
    line = next(item for item in dashboard["lines"] if item["status"] == "PENDING")
    initial_remaining = float(line["remaining_qty"])
    confirmed = sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [line["id"]]})
    assert confirmed.status_code == 200
    assert confirmed.json() == {"confirmed": 1, "outbound_mails": 1}
    assert sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [line["id"]]}).status_code == 409

    reversed_response = sales_client.post(f"/api/shipment-lines/{line['id']}/reverse", json={"reason": "客户修正发货数量"})
    assert reversed_response.status_code == 200
    assert reversed_response.json()["status"] == "REVERSED"
    orders = sales_client.get("/api/orders").json()
    order = next(item for item in orders if item["order_no"] == line["order_no"] and item["part_no"] == line["part_no"])
    assert float(order["remaining_qty"]) == initial_remaining
    with SessionLocal() as db:
        assert db.query(LedgerEntry).count() == 2
        assert db.query(OutboundMail).count() == 2


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证订单导入必须先预览后提交，并能写入标准字段。
def test_order_import_preview_and_commit(client: TestClient):
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Demo123!"})
    workbook = Workbook()
    sheet = workbook.active
    # CHANGE [2026-08-30 12:58 +08:00] [WH400]: 模拟正式模板前置标题与说明，验证解析器可定位第 3 行表头。
    sheet.append(["销售订单批量导入"])
    sheet.append(["仅管理员使用，上传后先预览。"])
    sheet.append(["代理商编码", "订单号", "零件号", "物料号", "品名", "订单数量", "单位", "品牌/供应商编码"])
    sheet.append(["JNTQ", "200020001", "TK10018", "TK10018X", "测试油品", 100, "桶", "DFL"])
    buffer = BytesIO()
    workbook.save(buffer)
    preview = client.post("/api/orders/import/preview", files={"file": ("orders.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert preview.status_code == 200
    assert preview.json()["error_count"] == 0
    committed = client.post(f"/api/orders/import/{preview.json()['token']}/commit")
    assert committed.status_code == 200
    assert committed.json()["imported"] == 1


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 验证管理员可维护供应商、物料与账号，同时普通销售无权读取配置。
def test_admin_master_data_permissions(client: TestClient):
    client.post("/api/auth/login", json={"email": "sales@example.com", "password": "Demo123!"})
    assert client.get("/api/admin/config").status_code == 403
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Demo123!"})
    supplier = client.post("/api/admin/suppliers", json={"code": "NEW", "name": "新增供应商", "email": "new-supplier@example.com"})
    assert supplier.status_code == 200
    material = client.post("/api/admin/materials", json={"material_no": "NEW001X", "part_no": "NEW001", "product_name": "新增测试油品", "brand_code": "NEW", "supplier_code": "NEW"})
    assert material.status_code == 200
    created_user = client.post("/api/admin/users", json={"email": "new-dealer-user@example.com", "display_name": "新增代理商用户", "password": "StrongPass123!", "role": "DEALER", "dealer_code": "JNTQ"})
    assert created_user.status_code == 200
    config = client.get("/api/admin/config").json()
    assert any(item["material_no"] == "NEW001X" for item in config["materials"])
    assert any(item["email"] == "new-dealer-user@example.com" for item in config["users"])


def test_mailbox_views_and_manual_retry(sales_client: TestClient):
    requests = sales_client.get("/api/shipment-requests")
    assert requests.status_code == 200
    assert requests.json()[0]["line_count"] >= 1
    line = next(item for item in sales_client.get("/api/shipment-lines").json() if item["status"] == "PENDING")
    assert sales_client.post("/api/shipment-lines/confirm", json={"line_ids": [line["id"]]}).status_code == 200
    outbound = sales_client.get("/api/outbound-mails")
    assert outbound.status_code == 200
    mail = outbound.json()[0]
    assert mail["status"] == "PENDING"
    assert sales_client.post(f"/api/outbound-mails/{mail['id']}/retry").status_code == 204


def test_admin_can_update_master_data_and_reset_user_password(client: TestClient):
    assert client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Demo123!"}).status_code == 200
    config = client.get("/api/admin/config").json()
    dealer = config["dealers"][0]
    supplier = config["suppliers"][0]
    material = config["materials"][0]
    assert client.patch(f"/api/admin/dealers/{dealer['id']}", json={"name": "更新后的代理商"}).status_code == 200
    assert client.patch(f"/api/admin/suppliers/{supplier['id']}", json={"email": "route-updated@example.com"}).status_code == 200
    assert client.patch(f"/api/admin/materials/{material['id']}", json={"product_name": "更新后的测试油品"}).status_code == 200

    created = client.post("/api/admin/users", json={"email": "operator", "display_name": "测试操作员", "password": "StrongPass123!", "role": "SALES"})
    assert created.status_code == 200
    user_id = created.json()["id"]
    updated = client.patch(f"/api/admin/users/{user_id}", json={"display_name": "更新操作员", "password": "UpdatedPass123!", "active": True})
    assert updated.status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "operator", "password": "UpdatedPass123!"}).status_code == 200


def test_admin_cannot_disable_current_account(client: TestClient):
    login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Demo123!"})
    admin_id = login.json()["id"]
    response = client.patch(f"/api/admin/users/{admin_id}", json={"active": False})
    assert response.status_code == 409
