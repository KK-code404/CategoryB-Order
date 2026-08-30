import asyncio
import json
from typing import Any

import httpx
from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import ShipmentLine, ShipmentStatus
from .audit import add_audit_event


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 仅向批准的 AI 服务发送非敏感字段，并把返回值限制为人工可确认的候选结果。
async def suggest_exception_fields(raw_row: dict[str, Any], reason: str) -> dict[str, Any] | None:
    if not settings.ai_api_url or not settings.ai_api_key or not settings.ai_model:
        return None
    safe_fields = {key: raw_row.get(key) for key in ("订单号", "物料号", "品名", "数量", "要求发货日期", "备注")}
    payload = {
        "model": settings.ai_model,
        "input": {"task": "提取并修正发货申请字段候选，不执行核销", "reason": reason, "fields": safe_fields},
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.ai_api_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(settings.ai_api_url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
    return result if isinstance(result, dict) else None


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 扫描异常行并只保存 AI 候选，绝不自动改写订单、数量或核销状态。
def enrich_exceptions_once() -> int:
    if not settings.ai_api_url or not settings.ai_api_key or not settings.ai_model:
        return 0
    enriched = 0
    with SessionLocal() as db:
        lines = db.scalars(select(ShipmentLine).where(ShipmentLine.status == ShipmentStatus.EXCEPTION, ShipmentLine.ai_suggestion_json.is_(None)).limit(10)).all()
        for line in lines:
            raw = {"订单号": line.order_no, "物料号": line.material_no, "品名": line.product_name, "数量": str(line.quantity), "要求发货日期": str(line.requested_ship_date), "备注": line.remark}
            try:
                suggestion = asyncio.run(suggest_exception_fields(raw, line.exception_reason or "规则匹配失败"))
                if suggestion:
                    line.ai_suggestion_json = json.dumps(suggestion, ensure_ascii=False)
                    confidence = suggestion.get("confidence")
                    if isinstance(confidence, (int, float)) and 0 <= confidence <= 1:
                        line.confidence = confidence
                    add_audit_event(db, actor=None, action="AI异常建议", object_type="ShipmentLine", object_id=str(line.id), detail="已生成候选字段，等待人工确认", dealer_id=line.request.dealer_id)
                    enriched += 1
            except Exception as exc:
                add_audit_event(db, actor=None, action="AI异常建议", object_type="ShipmentLine", object_id=str(line.id), detail=str(exc)[:500], dealer_id=line.request.dealer_id, result="失败")
        db.commit()
    return enriched
