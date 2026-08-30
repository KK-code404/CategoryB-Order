from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 固化三类用户权限边界，避免以页面隐藏替代服务端授权。
class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SALES = "SALES"
    DEALER = "DEALER"


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 统一发货行的可追溯状态机。
class ShipmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXCEPTION = "EXCEPTION"
    RECONCILED = "RECONCILED"
    REVERSED = "REVERSED"


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 区分正向核销与反向冲销，确保历史记录只追加不覆盖。
class LedgerType(str, enum.Enum):
    DEBIT = "DEBIT"
    REVERSAL = "REVERSAL"


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 独立管理供应商邮件生命周期，使发送失败不会回滚库存。
class MailStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 保存代理商身份及发件地址，支撑邮件归属识别和数据隔离。
class Dealer(Base):
    __tablename__ = "dealers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 保存邮箱账号和角色，密码只保留 Argon2 哈希。
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), index=True)
    dealer_id: Mapped[int | None] = mapped_column(ForeignKey("dealers.id"), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    dealer: Mapped[Dealer | None] = relationship()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 维护供应商发信路由，以品牌或物料映射自动决定收件人。
class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 显式维护物料号到零件号和供应商的映射，替代人工查表。
class MaterialMapping(Base):
    __tablename__ = "material_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    part_no: Mapped[str] = mapped_column(String(80), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    brand_code: Mapped[str] = mapped_column(String(50))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    supplier: Mapped[Supplier] = relationship()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 以订单行维护原始数量、累计核销量与乐观版本，支持余额校验和并发保护。
class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (UniqueConstraint("dealer_id", "order_no", "part_no", name="uq_dealer_order_part"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id"), index=True)
    order_no: Mapped[str] = mapped_column(String(80), index=True)
    part_no: Mapped[str] = mapped_column(String(80), index=True)
    material_no: Mapped[str] = mapped_column(String(80), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reconciled_qty: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    unit: Mapped[str] = mapped_column(String(20), default="桶")
    version: Mapped[int] = mapped_column(Integer, default=1)
    dealer: Mapped[Dealer] = relationship()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 保存邮件级幂等信息与原始附件证据，避免重复抓取产生重复核销。
class ShipmentRequest(Base):
    __tablename__ = "shipment_requests"
    __table_args__ = (UniqueConstraint("message_id", "attachment_sha256", name="uq_message_attachment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id"), index=True)
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    batch_no: Mapped[str] = mapped_column(String(80))
    message_id: Mapped[str] = mapped_column(String(255))
    imap_uid: Mapped[str] = mapped_column(String(80))
    uid_validity: Mapped[str] = mapped_column(String(80), default="")
    attachment_name: Mapped[str] = mapped_column(String(255))
    attachment_sha256: Mapped[str] = mapped_column(String(64), index=True)
    attachment_path: Mapped[str] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    dealer: Mapped[Dealer] = relationship()
    lines: Mapped[list[ShipmentLine]] = relationship(back_populates="request", cascade="all, delete-orphan")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将邮件内每条发货需求独立建模，以支持逐行确认和部分异常不阻塞。
class ShipmentLine(Base):
    __tablename__ = "shipment_lines"
    __table_args__ = (Index("ix_shipment_status_request", "status", "request_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("shipment_requests.id"), index=True)
    row_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_no: Mapped[str] = mapped_column(String(80), index=True)
    material_no: Mapped[str] = mapped_column(String(80), index=True)
    part_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    receiver: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(500))
    requested_ship_date: Mapped[date] = mapped_column(Date)
    remark: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ShipmentStatus] = mapped_column(Enum(ShipmentStatus, native_enum=False), index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    exception_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # CHANGE [2026-08-30 12:58 +08:00] [WH400]: 单独保存 AI 候选而不覆盖业务字段，确保人工确认前不会影响核销。
    ai_suggestion_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_order_line_id: Mapped[int | None] = mapped_column(ForeignKey("sales_order_lines.id"), nullable=True, index=True)
    request: Mapped[ShipmentRequest] = relationship(back_populates="lines")
    matched_order_line: Mapped[SalesOrderLine | None] = relationship()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 以追加式台账记录每次扣减和冲销，原核销记录永不覆盖。
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_line_id: Mapped[int] = mapped_column(ForeignKey("shipment_lines.id"), index=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_lines.id"), index=True)
    entry_type: Mapped[LedgerType] = mapped_column(Enum(LedgerType, native_enum=False))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500), default="")
    reverses_entry_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entries.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 使用事务外发箱保存供应商邮件，支持幂等、重试与失败告警。
class OutboundMail(Base):
    __tablename__ = "outbound_mails"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="SHIPMENT")
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    line_ids_json: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[MailStatus] = mapped_column(Enum(MailStatus, native_enum=False), default=MailStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 保存不可删除的业务审计事件，支持双方对账与责任追溯。
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(80), index=True)
    object_type: Mapped[str] = mapped_column(String(80), index=True)
    object_id: Mapped[str] = mapped_column(String(100), index=True)
    detail: Mapped[str] = mapped_column(Text)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(30), default="成功")
    ip_address: Mapped[str] = mapped_column(String(80), default="system")
    dealer_id: Mapped[int | None] = mapped_column(ForeignKey("dealers.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 暂存订单导入校验结果，使用户明确确认后才写入正式台账。
class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    error_json: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
