import json
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent, User


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将关键业务动作追加为结构化审计事件，并保留修改前后值。
def add_audit_event(
    db: Session,
    *,
    actor: User | None,
    action: str,
    object_type: str,
    object_id: str,
    detail: str,
    dealer_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    result: str = "成功",
    ip_address: str = "system",
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        actor_name=actor.display_name if actor else "系统",
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
        dealer_id=dealer_id,
        before_json=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after_json=json.dumps(after, ensure_ascii=False, default=str) if after else None,
        result=result,
        ip_address=ip_address,
    )
    db.add(event)
    return event

