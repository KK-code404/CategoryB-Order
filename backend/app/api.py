from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .db import get_db
from .models import AuditEvent, Dealer, LedgerEntry, LedgerType, MailStatus, MaterialMapping, OutboundMail, SalesOrderLine, ShipmentLine, ShipmentRequest, ShipmentStatus, Supplier, User, UserRole
from .schemas import (
    AuditEventOut,
    ConfirmLinesRequest,
    DashboardOut,
    DealerCreate,
    DealerUpdate,
    ImportPreviewOut,
    LoginRequest,
    MaterialMappingCreate,
    MaterialMappingUpdate,
    OrderLineOut,
    OutboundMailOut,
    ReverseRequest,
    ShipmentLineOut,
    ShipmentLineUpdate,
    ShipmentRequestOut,
    SupplierCreate,
    SupplierUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)
from .security import create_access_token, get_current_user, hash_password, require_roles, verify_password
from .services.audit import add_audit_event
from .services.excel_import import commit_order_import, preview_order_import
from .services.matching import match_shipment_line
from .services.material_names import MaterialCatalog, configured_product_name, material_catalog
from .services.reconciliation import confirm_lines, reverse_line
# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 引入只读每日汇总，复用登录授权且不暴露收货人或地址。
from .services.daily_shipments import daily_shipments
from .services.reconciliation_analytics import reconciliation_analytics
from .schemas import DailyShipmentReport

router = APIRouter(prefix=settings.api_prefix)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 统一获取真实客户端地址供安全审计，并兼容反向代理转发头。
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 构造发货行响应并按映射补充订单余额和供应商信息。
def _shipment_out(db: Session, line: ShipmentLine, catalog: MaterialCatalog | None = None) -> ShipmentLineOut:
    order = line.matched_order_line
    catalog = catalog or material_catalog(db)
    mapping = catalog[0].get(line.material_no)
    supplier = db.get(Supplier, mapping.supplier_id) if mapping else None
    remaining = Decimal(order.ordered_qty) - Decimal(order.reconciled_qty) if order else None
    return ShipmentLineOut(
        id=line.id, request_id=line.request_id, request_no=line.request.request_no, sender_email=line.request.sender_email,
        dealer_name=line.request.dealer.name, received_at=line.request.received_at, requested_ship_date=line.requested_ship_date,
        order_no=line.order_no, material_no=line.material_no, part_no=line.part_no,
        product_name=configured_product_name(catalog, line.material_no, line.part_no, line.product_name),
        quantity=line.quantity, receiver=line.receiver, phone=line.phone, address=line.address,
        remark="历史发货补录" if line.request.uid_validity == "approved-history" else line.remark,
        status=line.status, confidence=line.confidence, exception_reason=line.exception_reason,
        ai_suggestion_json=line.ai_suggestion_json,
        ordered_qty=order.ordered_qty if order else None, reconciled_qty=order.reconciled_qty if order else None,
        remaining_qty=remaining, supplier_name=supplier.name if supplier else None,
    )


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 应用代理商数据范围过滤，确保外部账号只能访问自身业务记录。
def _shipment_query(user: User):
    query = select(ShipmentLine).join(ShipmentRequest).options(joinedload(ShipmentLine.request).joinedload(ShipmentRequest.dealer), joinedload(ShipmentLine.matched_order_line)).order_by(ShipmentRequest.received_at.desc(), ShipmentLine.id.desc())
    return query.where(ShipmentRequest.dealer_id == user.dealer_id) if user.role == UserRole.DEALER else query


def _shipment_request_out(item: ShipmentRequest) -> ShipmentRequestOut:
    counts = {status: 0 for status in ShipmentStatus}
    for line in item.lines:
        counts[line.status] += 1
    return ShipmentRequestOut(
        id=item.id,
        request_no=item.request_no,
        sender_email=item.sender_email,
        dealer_name=item.dealer.name,
        subject=item.subject,
        batch_no=item.batch_no,
        attachment_name=item.attachment_name,
        received_at=item.received_at,
        line_count=len(item.lines),
        pending_count=counts[ShipmentStatus.PENDING],
        exception_count=counts[ShipmentStatus.EXCEPTION],
        reconciled_count=counts[ShipmentStatus.RECONCILED],
        reversed_count=counts[ShipmentStatus.REVERSED],
    )


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供轻量健康检查用于反向代理和虚拟机监控。
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


# CHANGE [2026-08-30 18:05 +08:00] [WH400]: 校验账号密码并设置严格同站 HttpOnly 会话 Cookie。
@router.post("/auth/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)) -> User:
    account = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == account, User.active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    response.set_cookie("access_token", create_access_token(user), httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=settings.access_token_minutes * 60, path="/")
    add_audit_event(db, actor=user, action="登录", object_type="User", object_id=str(user.id), detail="用户登录平台", dealer_id=user.dealer_id, ip_address=_client_ip(request))
    db.commit()
    return user


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 返回当前会话用户供前端恢复登录状态。
@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 清除服务端签名 Cookie，确保退出后浏览器不再携带会话。
@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("access_token", path="/")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 一次返回工作台统计、待处理明细和近期审计记录，减少首屏请求瀑布。
@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardOut:
    lines = db.scalars(_shipment_query(user).limit(50)).unique().all()
    catalog = material_catalog(db)
    visible = [_shipment_out(db, line, catalog) for line in lines]
    dealer_filter = ShipmentRequest.dealer_id == user.dealer_id if user.role == UserRole.DEALER else True
    pending_emails = db.scalar(select(func.count(func.distinct(ShipmentRequest.id))).join(ShipmentLine).where(dealer_filter, ShipmentLine.status.in_([ShipmentStatus.PENDING, ShipmentStatus.EXCEPTION]))) or 0
    exceptions = sum(1 for line in visible if line.status == ShipmentStatus.EXCEPTION)
    shanghai = ZoneInfo("Asia/Shanghai")
    local_start = datetime.combine(datetime.now(shanghai).date(), time.min, tzinfo=shanghai).astimezone(timezone.utc)
    ledger_query = select(func.count(LedgerEntry.id)).join(ShipmentLine).join(ShipmentRequest).where(LedgerEntry.entry_type == LedgerType.DEBIT, LedgerEntry.created_at >= local_start, dealer_filter)
    reconciled_today = db.scalar(ledger_query) or 0
    order_query = select(SalesOrderLine).options(joinedload(SalesOrderLine.dealer))
    if user.role == UserRole.DEALER:
        order_query = order_query.where(SalesOrderLine.dealer_id == user.dealer_id)
    orders = db.scalars(order_query).unique().all()
    remaining_stock = sum(Decimal(order.ordered_qty) - Decimal(order.reconciled_qty) for order in orders)
    audit_query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(5)
    if user.role == UserRole.DEALER:
        audit_query = audit_query.where(AuditEvent.dealer_id == user.dealer_id)
    audits = db.scalars(audit_query).all()
    return DashboardOut(stats={"pending_emails": pending_emails, "match_exceptions": exceptions, "reconciled_today": reconciled_today, "remaining_stock": float(remaining_stock), "material_count": len({order.material_no for order in orders})}, lines=visible, audit_events=[AuditEventOut.model_validate(item) for item in audits])


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 返回角色范围内的订单台账及实时计算余额。
@router.get("/orders", response_model=list[OrderLineOut])
def orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[OrderLineOut]:
    query = select(SalesOrderLine).options(joinedload(SalesOrderLine.dealer)).order_by(SalesOrderLine.order_no, SalesOrderLine.part_no)
    if user.role == UserRole.DEALER:
        query = query.where(SalesOrderLine.dealer_id == user.dealer_id)
    catalog = material_catalog(db)
    return [OrderLineOut(id=item.id, dealer_name=item.dealer.name, order_no=item.order_no, part_no=item.part_no, material_no=item.material_no, product_name=configured_product_name(catalog, item.material_no, item.part_no, item.product_name), ordered_qty=item.ordered_qty, reconciled_qty=item.reconciled_qty, remaining_qty=Decimal(item.ordered_qty) - Decimal(item.reconciled_qty), unit=item.unit, version=item.version) for item in db.scalars(query).unique().all()]


# CHANGE [2026-09-03 09:01 +08:00] [WH400]: 提供按月每日发货台账，服务端强制代理商隔离而不是依赖页面筛选。
@router.get("/orders/daily-shipments", response_model=DailyShipmentReport)
def order_daily_shipments(month: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DailyShipmentReport:
    return daily_shipments(db, user, month)


@router.get("/orders/reconciliation-analytics")
def order_reconciliation_analytics(start: date, end: date, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return reconciliation_analytics(db, user, start, end)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 返回角色范围内的全部发货行，供申请与收件箱页面共用。
@router.get("/shipment-lines", response_model=list[ShipmentLineOut])
def shipment_lines(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ShipmentLineOut]:
    catalog = material_catalog(db)
    return [_shipment_out(db, line, catalog) for line in db.scalars(_shipment_query(user)).unique().all()]


@router.get("/shipment-requests", response_model=list[ShipmentRequestOut])
def shipment_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ShipmentRequestOut]:
    query = select(ShipmentRequest).options(joinedload(ShipmentRequest.dealer), joinedload(ShipmentRequest.lines)).order_by(ShipmentRequest.received_at.desc())
    if user.role == UserRole.DEALER:
        query = query.where(ShipmentRequest.dealer_id == user.dealer_id)
    return [_shipment_request_out(item) for item in db.scalars(query).unique().all()]


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 允许代理商修改自身待处理行、销售修改任意待处理行，并在保存后重新匹配。
@router.patch("/shipment-lines/{line_id}", response_model=ShipmentLineOut)
def update_shipment_line(line_id: int, payload: ShipmentLineUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ShipmentLineOut:
    line = db.scalar(_shipment_query(user).where(ShipmentLine.id == line_id))
    if not line:
        raise HTTPException(status_code=404, detail="发货明细不存在")
    if line.status not in (ShipmentStatus.PENDING, ShipmentStatus.EXCEPTION):
        raise HTTPException(status_code=409, detail="已核销明细不能直接修改，请使用冲销")
    before = {field: str(getattr(line, field)) for field in payload.model_fields_set}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    match_shipment_line(db, line)
    after = {field: str(getattr(line, field)) for field in payload.model_fields_set}
    add_audit_event(db, actor=user, action="修改申请", object_type="ShipmentLine", object_id=str(line.id), detail="修改待处理申请并重新匹配", dealer_id=line.request.dealer_id, before=before, after=after, ip_address=_client_ip(request))
    db.commit()
    db.refresh(line)
    return _shipment_out(db, line)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 仅销售或管理员可确认核销，并返回生成的供应商邮件数量。
@router.post("/shipment-lines/confirm")
def confirm(payload: ConfirmLinesRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES))) -> dict[str, int]:
    confirmed, outbound = confirm_lines(db, user, payload.line_ids, _client_ip(request))
    return {"confirmed": confirmed, "outbound_mails": outbound}


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 仅销售或管理员可通过反向流水更正已核销明细。
@router.post("/shipment-lines/{line_id}/reverse", response_model=ShipmentLineOut)
def reverse(line_id: int, payload: ReverseRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES))) -> ShipmentLineOut:
    line = db.scalar(_shipment_query(user).where(ShipmentLine.id == line_id))
    if not line:
        raise HTTPException(status_code=404, detail="发货明细不存在")
    reverse_line(db, user, line, payload.reason, _client_ip(request))
    return _shipment_out(db, line)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 按角色返回可见审计记录，代理商不接触其他客户或系统管理事件。
@router.get("/audit-events", response_model=list[AuditEventOut])
def audit_events(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(500)
    if user.role == UserRole.DEALER:
        query = query.where(AuditEvent.dealer_id == user.dealer_id)
    return list(db.scalars(query).all())


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 管理员上传订单 Excel 后仅生成校验预览，不立即写入订单台账。
@router.post("/orders/import/preview", response_model=ImportPreviewOut)
async def import_preview(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> ImportPreviewOut:
    content = await file.read()
    try:
        job = preview_order_import(db, user, content, file.filename or "orders.xlsx")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    import json
    errors = json.loads(job.error_json)
    return ImportPreviewOut(token=job.token, valid_count=len(json.loads(job.payload_json)), error_count=len(errors), errors=errors)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 管理员确认无错误的预览令牌后才提交订单数据。
@router.post("/orders/import/{token}/commit")
def import_commit(token: str, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    try:
        return {"imported": commit_order_import(db, user, token)}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 允许销售或管理员将失败邮件重新置入发送队列，保留既有尝试次数。
@router.post("/outbound-mails/{mail_id}/retry", status_code=204)
def retry_mail(mail_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES))) -> None:
    mail = db.get(OutboundMail, mail_id)
    if not mail:
        raise HTTPException(status_code=404, detail="邮件记录不存在")
    if mail.status == MailStatus.SENT:
        raise HTTPException(status_code=409, detail="邮件已发送成功，无需重试")
    mail.status = MailStatus.PENDING
    mail.last_error = None
    add_audit_event(db, actor=user, action="邮件重试", object_type="OutboundMail", object_id=str(mail.id), detail="人工重新加入发送队列")
    db.commit()


@router.get("/outbound-mails", response_model=list[OutboundMailOut])
def outbound_mails(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES))) -> list[OutboundMail]:
    return list(db.scalars(select(OutboundMail).order_by(OutboundMail.created_at.desc()).limit(500)).all())


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 一次返回管理员配置清单，减少配置页多接口请求并便于核对路由关系。
@router.get("/admin/config")
def admin_config(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))) -> dict:
    return {
        "dealers": [{"id": item.id, "code": item.code, "name": item.name, "email": item.email, "active": item.active} for item in db.scalars(select(Dealer).order_by(Dealer.code)).all()],
        "suppliers": [{"id": item.id, "code": item.code, "name": item.name, "email": item.email, "active": item.active} for item in db.scalars(select(Supplier).order_by(Supplier.code)).all()],
        "materials": [{"id": item.id, "material_no": item.material_no, "part_no": item.part_no, "product_name": item.product_name, "brand_code": item.brand_code, "supplier_code": item.supplier.code} for item in db.scalars(select(MaterialMapping).options(joinedload(MaterialMapping.supplier)).order_by(MaterialMapping.material_no)).unique().all()],
        "users": [{"id": item.id, "email": item.email, "display_name": item.display_name, "role": item.role.value, "dealer_code": item.dealer.code if item.dealer else None, "active": item.active} for item in db.scalars(select(User).options(joinedload(User.dealer)).order_by(User.email)).unique().all()],
    }


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 新增代理商并记录其邮件归属地址，唯一性冲突以业务提示返回。
@router.post("/admin/dealers")
def create_dealer(payload: DealerCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    dealer = Dealer(code=payload.code.strip().upper(), name=payload.name.strip(), email=payload.email.lower())
    db.add(dealer)
    add_audit_event(db, actor=user, action="新增代理商", object_type="Dealer", object_id=dealer.code, detail=f"创建代理商 {dealer.name}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="代理商编码或邮箱已存在") from exc
    return {"id": dealer.id}


@router.patch("/admin/dealers/{dealer_id}")
def update_dealer(dealer_id: int, payload: DealerUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    dealer = db.get(Dealer, dealer_id)
    if not dealer:
        raise HTTPException(status_code=404, detail="代理商不存在")
    before = {field: str(getattr(dealer, field)) for field in payload.model_fields_set}
    values = payload.model_dump(exclude_unset=True)
    if "code" in values:
        values["code"] = values["code"].strip().upper()
    if "name" in values:
        values["name"] = values["name"].strip()
    if "email" in values:
        values["email"] = str(values["email"]).lower()
    for field, value in values.items():
        setattr(dealer, field, value)
    add_audit_event(db, actor=user, action="修改代理商", object_type="Dealer", object_id=str(dealer.id), detail=f"更新代理商 {dealer.code}", before=before, after=values, dealer_id=dealer.id, ip_address=_client_ip(request))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="代理商编码或邮箱已存在") from exc
    return {"id": dealer.id}


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 新增供应商收件路由并写入审计事件。
@router.post("/admin/suppliers")
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    supplier = Supplier(code=payload.code.strip().upper(), name=payload.name.strip(), email=payload.email.lower())
    db.add(supplier)
    add_audit_event(db, actor=user, action="新增供应商", object_type="Supplier", object_id=supplier.code, detail=f"创建供应商路由 {supplier.email}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="供应商编码已存在") from exc
    return {"id": supplier.id}


@router.patch("/admin/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    before = {field: str(getattr(supplier, field)) for field in payload.model_fields_set}
    values = payload.model_dump(exclude_unset=True)
    if "code" in values:
        values["code"] = values["code"].strip().upper()
    if "name" in values:
        values["name"] = values["name"].strip()
    if "email" in values:
        values["email"] = str(values["email"]).lower()
    for field, value in values.items():
        setattr(supplier, field, value)
    add_audit_event(db, actor=user, action="修改供应商", object_type="Supplier", object_id=str(supplier.id), detail=f"更新供应商 {supplier.code}", before=before, after=values, ip_address=_client_ip(request))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="供应商编码已存在") from exc
    return {"id": supplier.id}


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 新增物料映射并验证供应商编码存在，确保后续核销可自动发信。
@router.post("/admin/materials")
def create_material(payload: MaterialMappingCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    supplier = db.scalar(select(Supplier).where(Supplier.code == payload.supplier_code.strip().upper(), Supplier.active.is_(True)))
    if not supplier:
        raise HTTPException(status_code=400, detail="供应商编码不存在")
    mapping = MaterialMapping(material_no=payload.material_no.strip().upper(), part_no=payload.part_no.strip().upper(), product_name=payload.product_name.strip(), brand_code=payload.brand_code.strip().upper(), supplier_id=supplier.id)
    db.add(mapping)
    add_audit_event(db, actor=user, action="新增物料映射", object_type="MaterialMapping", object_id=mapping.material_no, detail=f"映射至零件 {mapping.part_no} 和供应商 {supplier.code}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="物料号已存在") from exc
    return {"id": mapping.id}


@router.patch("/admin/materials/{material_id}")
def update_material(material_id: int, payload: MaterialMappingUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    mapping = db.get(MaterialMapping, material_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="物料映射不存在")
    values = payload.model_dump(exclude_unset=True)
    supplier_code = values.pop("supplier_code", None)
    before = {field: str(getattr(mapping, field)) for field in payload.model_fields_set if field != "supplier_code"}
    before["supplier_code"] = mapping.supplier.code
    if supplier_code is not None:
        supplier = db.scalar(select(Supplier).where(Supplier.code == supplier_code.strip().upper(), Supplier.active.is_(True)))
        if not supplier:
            raise HTTPException(status_code=400, detail="供应商编码不存在或已停用")
        mapping.supplier_id = supplier.id
    for field in ("material_no", "part_no", "brand_code"):
        if field in values:
            values[field] = values[field].strip().upper()
    if "product_name" in values:
        values["product_name"] = values["product_name"].strip()
    for field, value in values.items():
        setattr(mapping, field, value)
    after = {**values, "supplier_code": supplier_code.strip().upper() if supplier_code is not None else mapping.supplier.code}
    add_audit_event(db, actor=user, action="修改物料映射", object_type="MaterialMapping", object_id=str(mapping.id), detail=f"更新物料 {mapping.material_no}", before=before, after=after, ip_address=_client_ip(request))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="物料号已存在") from exc
    return {"id": mapping.id}


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 新增邮箱密码账号并强制代理商角色绑定数据范围。
@router.post("/admin/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    dealer = None
    if payload.role == UserRole.DEALER:
        if not payload.dealer_code:
            raise HTTPException(status_code=400, detail="代理商账号必须选择代理商")
        dealer = db.scalar(select(Dealer).where(Dealer.code == payload.dealer_code.strip().upper(), Dealer.active.is_(True)))
        if not dealer:
            raise HTTPException(status_code=400, detail="代理商编码不存在")
    user = User(email=payload.email.lower(), display_name=payload.display_name.strip(), password_hash=hash_password(payload.password), role=payload.role, dealer_id=dealer.id if dealer else None)
    db.add(user)
    add_audit_event(db, actor=actor, action="新增用户", object_type="User", object_id=user.email, detail=f"创建 {payload.role.value} 账号")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户邮箱已存在") from exc
    return {"id": user.id}


@router.patch("/admin/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, int]:
    target = db.scalar(select(User).options(joinedload(User.dealer)).where(User.id == user_id))
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    values = payload.model_dump(exclude_unset=True)
    if target.id == actor.id and (values.get("active") is False or (values.get("role") is not None and values["role"] != UserRole.ADMIN)):
        raise HTTPException(status_code=409, detail="不能停用当前账号或移除自身管理员角色")

    target_role = values.get("role", target.role)
    dealer_code = values.pop("dealer_code", None)
    if target_role == UserRole.DEALER:
        dealer = target.dealer
        if dealer_code is not None:
            dealer = db.scalar(select(Dealer).where(Dealer.code == dealer_code.strip().upper(), Dealer.active.is_(True)))
        if not dealer:
            raise HTTPException(status_code=400, detail="代理商账号必须绑定有效代理商")
        target.dealer_id = dealer.id
    else:
        target.dealer_id = None

    before = {"email": target.email, "display_name": target.display_name, "role": target.role.value, "dealer_code": target.dealer.code if target.dealer else None, "active": target.active}
    password = values.pop("password", None)
    if "email" in values:
        values["email"] = values["email"].strip().lower()
    if "display_name" in values:
        values["display_name"] = values["display_name"].strip()
    for field, value in values.items():
        setattr(target, field, value)
    if password:
        target.password_hash = hash_password(password)
    after = {"email": target.email, "display_name": target.display_name, "role": target.role.value, "dealer_code": dealer_code, "active": target.active, "password_reset": bool(password)}
    add_audit_event(db, actor=actor, action="修改用户", object_type="User", object_id=str(target.id), detail=f"更新账号 {target.email}", before=before, after=after, ip_address=_client_ip(request))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户账号已存在") from exc
    return {"id": target.id}
