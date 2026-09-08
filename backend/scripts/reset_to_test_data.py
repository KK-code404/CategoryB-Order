"""Replace all business records with the built-in synthetic test dataset."""

from sqlalchemy import delete, func, select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    AuditEvent,
    Dealer,
    ImportJob,
    LedgerEntry,
    MaterialMapping,
    OutboundMail,
    SalesOrderLine,
    ShipmentLine,
    ShipmentRequest,
    Supplier,
    User,
    UserRole,
)
from app.seed import seed_database


def main() -> None:
    if not settings.initial_admin_password and not settings.seed_demo_data:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD or SEED_DEMO_DATA is required before resetting data")

    with SessionLocal() as db:
        admins = [
            {
                "email": user.email,
                "display_name": user.display_name,
                "password_hash": user.password_hash,
                "active": user.active,
                "created_at": user.created_at,
            }
            for user in db.scalars(select(User).where(User.role == UserRole.ADMIN)).all()
        ]
        if not admins:
            raise RuntimeError("No administrator account found; reset aborted")

        for model in (
            OutboundMail,
            LedgerEntry,
            AuditEvent,
            ShipmentLine,
            ShipmentRequest,
            ImportJob,
            SalesOrderLine,
            MaterialMapping,
            User,
            Dealer,
            Supplier,
        ):
            db.execute(delete(model))
        db.flush()
        seed_database(db)

        seeded_admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
        if seeded_admin is None:
            raise RuntimeError("Synthetic seed did not create an administrator")
        primary = admins[0]
        for field, value in primary.items():
            setattr(seeded_admin, field, value)
        for saved in admins[1:]:
            db.add(User(role=UserRole.ADMIN, dealer_id=None, **saved))
        db.commit()

        counts = {
            "users": db.scalar(select(func.count()).select_from(User)),
            "dealers": db.scalar(select(func.count()).select_from(Dealer)),
            "orders": db.scalar(select(func.count()).select_from(SalesOrderLine)),
            "requests": db.scalar(select(func.count()).select_from(ShipmentRequest)),
            "lines": db.scalar(select(func.count()).select_from(ShipmentLine)),
            "ledger": db.scalar(select(func.count()).select_from(LedgerEntry)),
            "outbound_mail": db.scalar(select(func.count()).select_from(OutboundMail)),
        }
        print(counts)


if __name__ == "__main__":
    main()
