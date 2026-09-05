from sqlalchemy import select

from app.db import SessionLocal
from app.models import MaterialMapping


def test_configured_product_names_are_authoritative_on_workbench_and_orders(sales_client):
    with SessionLocal.begin() as db:
        mappings = db.scalars(select(MaterialMapping)).all()
        for mapping in mappings:
            mapping.product_name = f"配置品名-{mapping.material_no}"
        expected_by_material = {mapping.material_no: mapping.product_name for mapping in mappings}
        expected_by_part = {mapping.part_no: mapping.product_name for mapping in mappings}

    dashboard = sales_client.get('/api/dashboard')
    orders = sales_client.get('/api/orders')
    assert dashboard.status_code == orders.status_code == 200
    configured_lines = [line for line in dashboard.json()['lines'] if line['material_no'] in expected_by_material]
    assert configured_lines
    assert all(line['product_name'] == expected_by_material[line['material_no']] for line in configured_lines)
    configured_orders = [order for order in orders.json() if order['material_no'] in expected_by_material or order['part_no'] in expected_by_part]
    assert configured_orders
    for order in configured_orders:
        expected = expected_by_material.get(order['material_no'], expected_by_part[order['part_no']])
        assert order['product_name'] == expected
