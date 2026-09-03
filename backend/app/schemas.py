from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer

from .models import MailStatus, ShipmentStatus, UserRole


# CHANGE [2026-08-30 18:05 +08:00] [WH400]: 登录标识同时兼容简短账号和既有邮箱账号。
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 仅向前端暴露必要用户字段，不返回密码哈希。
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role: UserRole
    dealer_id: int | None


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 返回订单余额及版本，方便界面显示并发后的最新数据。
class OrderLineOut(BaseModel):
    id: int
    dealer_name: str
    order_no: str
    part_no: str
    material_no: str
    product_name: str
    ordered_qty: Decimal
    reconciled_qty: Decimal
    remaining_qty: Decimal
    unit: str
    version: int


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 聚合邮件、匹配订单与供应商信息供工作台一次渲染。
class ShipmentLineOut(BaseModel):
    id: int
    request_id: int
    request_no: str
    sender_email: str
    dealer_name: str
    received_at: datetime
    requested_ship_date: date
    order_no: str
    material_no: str
    part_no: str | None
    product_name: str
    quantity: Decimal
    receiver: str
    phone: str
    address: str
    remark: str
    status: ShipmentStatus
    confidence: Decimal | None
    exception_reason: str | None
    ai_suggestion_json: str | None
    ordered_qty: Decimal | None
    reconciled_qty: Decimal | None
    remaining_qty: Decimal | None
    supplier_name: str | None

    # CHANGE [2026-08-30 12:58 +08:00] [WH400]: 为 SQLite 丢失时区的时间补回 UTC 标记，保证前端可正确转换上海时间。
    @field_serializer("received_at")
    def serialize_received_at(self, value: datetime) -> str:
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return normalized.isoformat()


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 显式区分全期余额、本月合计及历史未分日数量，保持十进制精度。
class DailyShipmentRow(OrderLineOut):
    dealer_id: int
    dealer_code: str
    undated_qty: Decimal
    month_qty: Decimal
    daily: dict[str, Decimal]


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 返回包含无发货日的完整自然月列，供 Excel 式台账使用。
class DailyShipmentReport(BaseModel):
    month: str
    date_basis: str = "requested_ship_date"
    dates: list[str]
    rows: list[DailyShipmentRow]


class ShipmentRequestOut(BaseModel):
    id: int
    request_no: str
    sender_email: str
    dealer_name: str
    subject: str
    batch_no: str
    attachment_name: str
    received_at: datetime
    line_count: int
    pending_count: int
    exception_count: int
    reconciled_count: int
    reversed_count: int

    @field_serializer("received_at")
    def serialize_received_at(self, value: datetime) -> str:
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return normalized.isoformat()


class OutboundMailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    recipient: str
    subject: str
    status: MailStatus
    attempts: int
    last_error: str | None
    sent_at: datetime | None
    created_at: datetime

    @field_serializer("sent_at", "created_at")
    def serialize_mail_time(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return normalized.isoformat()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 限制待处理申请可修改字段，禁止客户端直接篡改状态和余额。
class ShipmentLineUpdate(BaseModel):
    order_no: str | None = Field(default=None, max_length=80)
    material_no: str | None = Field(default=None, max_length=80)
    product_name: str | None = Field(default=None, max_length=255)
    quantity: Decimal | None = Field(default=None, gt=0)
    receiver: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    requested_ship_date: date | None = None
    remark: str | None = Field(default=None, max_length=1000)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 支持销售一次确认多条正常明细并按供应商分组发信。
class ConfirmLinesRequest(BaseModel):
    line_ids: list[int] = Field(min_length=1, max_length=100)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 强制冲销填写原因以满足后续审计追溯。
class ReverseRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 统一向界面提供操作事件字段。
class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    actor_name: str
    action: str
    object_type: str
    object_id: str
    detail: str
    result: str

    # CHANGE [2026-08-30 12:58 +08:00] [WH400]: 审计时间统一输出带时区 ISO 文本，避免虚拟机与浏览器时区不一致。
    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return normalized.isoformat()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将工作台统计和首屏列表打包返回，避免串行请求瀑布。
class DashboardOut(BaseModel):
    stats: dict[str, int | float]
    lines: list[ShipmentLineOut]
    audit_events: list[AuditEventOut]


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 返回订单导入预览令牌和逐行错误，写入前由用户确认。
class ImportPreviewOut(BaseModel):
    token: str
    valid_count: int
    error_count: int
    errors: list[dict[str, str | int]]


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 校验新增代理商基础资料并使用邮箱作为邮件归属依据。
class DealerCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr


class DealerUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=50)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    active: bool | None = None


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 校验供应商路由目标，避免缺少收件邮箱的配置进入发送队列。
class SupplierCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=50)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    active: bool | None = None


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 校验物料到零件与供应商的显式映射输入。
class MaterialMappingCreate(BaseModel):
    material_no: str = Field(min_length=2, max_length=80)
    part_no: str = Field(min_length=2, max_length=80)
    product_name: str = Field(min_length=2, max_length=255)
    brand_code: str = Field(min_length=2, max_length=50)
    supplier_code: str = Field(min_length=2, max_length=50)


class MaterialMappingUpdate(BaseModel):
    material_no: str | None = Field(default=None, min_length=2, max_length=80)
    part_no: str | None = Field(default=None, min_length=2, max_length=80)
    product_name: str | None = Field(default=None, min_length=2, max_length=255)
    brand_code: str | None = Field(default=None, min_length=2, max_length=50)
    supplier_code: str | None = Field(default=None, min_length=2, max_length=50)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 校验新用户角色与初始密码，代理商账号需由服务端绑定客户范围。
class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=10, max_length=128)
    role: UserRole
    dealer_code: str | None = Field(default=None, max_length=50)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    password: str | None = Field(default=None, min_length=10, max_length=128)
    role: UserRole | None = None
    dealer_code: str | None = Field(default=None, max_length=50)
    active: bool | None = None
