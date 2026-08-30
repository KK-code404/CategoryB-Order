from celery import Celery

from .config import settings
from .services.ai_parser import enrich_exceptions_once
from .services.mail_ingest import poll_imap_once
from .services.outbound import dispatch_pending_mails


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将邮箱轮询和供应商发信配置为独立可重试任务，避免阻塞 Web 请求。
celery_app = Celery("categoryb_order", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "poll-imap-every-minute": {"task": "app.worker.poll_imap", "schedule": 60.0},
        "dispatch-mail-every-30-seconds": {"task": "app.worker.dispatch_mail", "schedule": 30.0},
        "enrich-exceptions-every-two-minutes": {"task": "app.worker.enrich_exceptions", "schedule": 120.0},
    },
)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 包装 IMAP 轮询为可观测的定时任务。
@celery_app.task(name="app.worker.poll_imap", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def poll_imap() -> int:
    return poll_imap_once()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 周期性发送外发箱邮件，单封失败由记录自身控制最多五次尝试。
@celery_app.task(name="app.worker.dispatch_mail")
def dispatch_mail() -> int:
    return dispatch_pending_mails()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 异步生成异常字段候选，确保 AI 延迟不会阻塞邮件入库和人工处理。
@celery_app.task(name="app.worker.enrich_exceptions")
def enrich_exceptions() -> int:
    return enrich_exceptions_once()
