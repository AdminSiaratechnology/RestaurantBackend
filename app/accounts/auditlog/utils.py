from app.accounts.auditlog.model import AuditLog
from app.db.config import SessionDep


async def log_action(
    db: SessionDep,
    current: dict | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    old_data: dict | None = None,
    new_data: dict | None = None,
    ip: str | None = None
):
    log = AuditLog(
        user_id=current["user"].id if current else None,
        user_role=current["role"] if current else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip
    )

    db.add(log)