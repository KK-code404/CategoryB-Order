"""Initial schema for the shipment reconciliation platform."""

from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision = "20260830_1258"
down_revision = None
branch_labels = None
depends_on = None


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 创建首版完整业务模型，确保空 PostgreSQL 可直接部署。
def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 为受控回滚提供逆向迁移入口，生产执行前必须先备份。
def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

