from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .config import settings
from .db import Base, SessionLocal, engine
from .seed import seed_database


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 启动时确保本地开发数据库可用，并按配置创建首个管理员或演示数据。
@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        seed_database(db)
    yield


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 创建受统一前缀保护的 FastAPI 应用，并只允许本地开发源携带会话。
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(router)

