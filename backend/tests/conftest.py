import os

# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 在导入应用前固定隔离数据库与演示种子，避免测试触碰真实业务数据。
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["COOKIE_SECURE"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_database


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 每个测试重建并填充数据库，保证用例互不依赖且结果可重复。
@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    with TestClient(app) as test_client:
        yield test_client


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 复用销售登录步骤，让业务测试只关注核销结果。
@pytest.fixture()
def sales_client(client: TestClient):
    response = client.post("/api/auth/login", json={"email": "sales@example.com", "password": "Demo123!"})
    assert response.status_code == 200
    return client

