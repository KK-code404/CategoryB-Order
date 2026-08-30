import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import MailStatus, OutboundMail
from .audit import add_audit_event


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 使用平台 SMTP 账号发送单条外发箱记录，并将发送结果写回审计日志。
def send_outbound_mail(mail_id: int) -> bool:
    with SessionLocal() as db:
        mail = db.scalar(select(OutboundMail).where(OutboundMail.id == mail_id).with_for_update())
        if not mail or mail.status == MailStatus.SENT:
            return True
        if not settings.smtp_host or not settings.smtp_from:
            mail.status = MailStatus.FAILED
            mail.last_error = "SMTP 未配置"
            mail.attempts += 1
            db.commit()
            return False

        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = mail.recipient
        message["Subject"] = mail.subject
        message["X-Idempotency-Key"] = mail.idempotency_key
        message.set_content(mail.body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
                if settings.smtp_starttls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
            mail.status = MailStatus.SENT
            mail.sent_at = datetime.now(timezone.utc)
            mail.last_error = None
            mail.attempts += 1
            add_audit_event(db, actor=None, action="供应商邮件发送", object_type="OutboundMail", object_id=str(mail.id), detail=f"发送至 {mail.recipient}")
            db.commit()
            return True
        except Exception as exc:
            mail.status = MailStatus.FAILED
            mail.attempts += 1
            mail.last_error = str(exc)[:1000]
            add_audit_event(db, actor=None, action="供应商邮件发送", object_type="OutboundMail", object_id=str(mail.id), detail=mail.last_error, result="失败")
            db.commit()
            raise


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 扫描待发送与可重试邮件，单封失败不阻塞其他供应商通知。
def dispatch_pending_mails() -> int:
    with SessionLocal() as db:
        ids = db.scalars(select(OutboundMail.id).where(OutboundMail.status.in_([MailStatus.PENDING, MailStatus.FAILED]), OutboundMail.attempts < 5).limit(50)).all()
    sent = 0
    for mail_id in ids:
        try:
            sent += int(send_outbound_mail(mail_id))
        except Exception:
            continue
    return sent

