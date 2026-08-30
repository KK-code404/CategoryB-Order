from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 为模型提供统一声明基类，确保迁移与运行时元数据一致。
class Base(DeclarativeBase):
    pass


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 同时支持本地 SQLite 验证和虚拟机 PostgreSQL 运行。
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 对每个 API 请求创建并可靠关闭独立数据库会话。
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

