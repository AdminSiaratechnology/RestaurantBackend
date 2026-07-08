import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from fastapi import Request, HTTPException
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.enum import UserRole
from app.accounts.client.model import Client
from .model import AuditLog

logger = logging.getLogger(__name__)

# Helper to map class names or roles to table names
_ACTOR_TABLE_MAP = {
    "super_admin": "superadmins",
    "partner": "partners",
    "client": "clients",
    "staff": "staffs",
}

# ==========================================================
# Reusable Auditing Helper
# ==========================================================

async def create_audit_log(
    db: AsyncSession,
    actor: Any,  # Dict from dependencies {"user": user, "role": role}, ORM instance, "system", or None
    action: str,
    module: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    status: str = "success",
    request: Optional[Request] = None
) -> Optional[AuditLog]:
    """
    Core helper function to log important actions inside the Restaurant Management System.
    Ensures robust extraction of client requests and actor details.
    """
    actor_type = "system"
    actor_id = None
    actor_name = None
    actor_email = None

    # 1. Parse Actor Details
    if isinstance(actor, dict):
        user = actor.get("user")
        role = actor.get("role")
        if user:
            actor_id = getattr(user, "id", None)
            actor_name = getattr(user, "name", None)
            actor_email = getattr(user, "email", None)
        if role:
            actor_type = getattr(role, "value", str(role))
    elif actor and actor != "system":
        # Direct ORM object
        actor_id = getattr(actor, "id", None)
        actor_name = getattr(actor, "name", None)
        actor_email = getattr(actor, "email", None)
        
        cls_name = actor.__class__.__name__.lower()
        if cls_name == "superadmin":
            actor_type = "super_admin"
        elif cls_name in ["partner", "client", "staff"]:
            actor_type = cls_name
        else:
            actor_type = cls_name

    # 2. Parse Request details
    ip_address = None
    user_agent = None
    request_method = None
    endpoint = None

    if request:
        from .utils import get_client_ip
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        request_method = request.method
        endpoint = request.url.path

    # 3. Create log entry
    try:
        log_entry = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_email=actor_email,
            action=action,
            module=module,
            table_name=table_name or _ACTOR_TABLE_MAP.get(actor_type),
            record_id=record_id,
            description=description,
            old_data=old_data,
            new_data=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            endpoint=endpoint,
            status=status
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        return log_entry
    except Exception as e:
        # Avoid breaking target request if auditing fails
        await db.rollback()
        logger.error(f"Failed to create audit log: {e}", exc_info=True)
        return None

# ==========================================================
# Service Layer Functions
# ==========================================================

async def get_paginated_logs(
    db: AsyncSession,
    current_user: Dict[str, Any],
    *,
    page: int = 1,
    page_size: int = 20,
    actor_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    module: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    sort: str = "newest",
) -> Tuple[List[AuditLog], int]:
    """
    List logs with search filters, sorting, and user-role-scoping.
    """
    q = select(AuditLog)

    # Scoping filter
    role = current_user["role"]
    user = current_user["user"]

    if role == UserRole.PARTNER:
        client_ids_subquery = select(Client.id).where(Client.partner_id == user.id)
        scope_filter = or_(
            and_(AuditLog.actor_type == "partner", AuditLog.actor_id == user.id),
            and_(AuditLog.actor_type == "client", AuditLog.actor_id.in_(client_ids_subquery))
        )
        q = q.where(scope_filter)
    elif role == UserRole.CLIENT:
        raise HTTPException(status_code=403, detail="Clients cannot access audit logs")

    # Optional Filters
    if actor_type:
        q = q.where(AuditLog.actor_type == actor_type)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    if module:
        q = q.where(AuditLog.module.ilike(f"%{module}%"))
    if table_name:
        q = q.where(AuditLog.table_name == table_name)
    if record_id:
        q = q.where(AuditLog.record_id == record_id)
    if status:
        q = q.where(AuditLog.status == status)
    if from_date:
        q = q.where(AuditLog.created_at >= from_date)
    if to_date:
        q = q.where(AuditLog.created_at <= to_date)

    # Compute Total count
    count_q = select(func.count()).select_from(q.subquery())
    total_records = (await db.execute(count_q)).scalar_one()

    # Sort
    if sort == "oldest":
        q = q.order_by(AuditLog.created_at.asc())
    else:
        q = q.order_by(AuditLog.created_at.desc())

    # Paginate
    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)

    result = await db.execute(q)
    return result.scalars().all(), total_records


async def get_log_by_id(db: AsyncSession, current_user: Dict[str, Any], log_id: int) -> Optional[AuditLog]:
    """
    Fetch audit log details with proper scoping validation.
    """
    stmt = select(AuditLog).where(AuditLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return None

    role = current_user["role"]
    user = current_user["user"]

    if role == UserRole.PARTNER:
        if log.actor_type == "partner" and log.actor_id == user.id:
            return log
        elif log.actor_type == "client":
            client_belongs = await db.scalar(
                select(func.count(Client.id))
                .where(Client.id == log.actor_id, Client.partner_id == user.id)
            )
            if client_belongs > 0:
                return log
        raise HTTPException(status_code=403, detail="You are not authorized to view this log record")
    elif role == UserRole.CLIENT:
        raise HTTPException(status_code=403, detail="Clients cannot access audit logs")

    return log


async def get_recent_logs(db: AsyncSession, current_user: Dict[str, Any], limit: int = 20) -> List[AuditLog]:
    """
    Get recent audit logs.
    """
    q = select(AuditLog)

    role = current_user["role"]
    user = current_user["user"]

    if role == UserRole.PARTNER:
        client_ids_subquery = select(Client.id).where(Client.partner_id == user.id)
        scope_filter = or_(
            and_(AuditLog.actor_type == "partner", AuditLog.actor_id == user.id),
            and_(AuditLog.actor_type == "client", AuditLog.actor_id.in_(client_ids_subquery))
        )
        q = q.where(scope_filter)

    q = q.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


async def get_dashboard_summary(db: AsyncSession, current_user: Dict[str, Any]) -> Dict[str, int]:
    """
    Get audit stats summary today.
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    role = current_user["role"]
    user = current_user["user"]

    def build_scoped_query(action_filter=None, status_filter=None, unique_actors=False):
        if unique_actors:
            stmt = select(func.count(func.distinct(AuditLog.actor_id)))
        else:
            stmt = select(func.count(AuditLog.id))
        
        stmt = select(func.count()).select_from(AuditLog)

        if action_filter:
            stmt = stmt.where(AuditLog.action == action_filter)
        # if status_filter:
        #     stmt = stmt.where(AuditLog.status == status_filter)

        if role == UserRole.PARTNER:
            client_ids_subquery = select(Client.id).where(Client.partner_id == user.id)
            scope_filter = or_(
                and_(AuditLog.actor_type == "partner", AuditLog.actor_id == user.id),
                and_(AuditLog.actor_type == "client", AuditLog.actor_id.in_(client_ids_subquery))
            )
            stmt = stmt.where(scope_filter)

        return stmt

    # logins = await db.scalar(build_scoped_query(action_filter="login", status_filter="success")) or 0
    logins = await db.scalar(
        build_scoped_query(
            action_filter="login"
        )
    ) or 0
    logouts = await db.scalar(build_scoped_query(action_filter="logout")) or 0
    failed_logins = await db.scalar(build_scoped_query(action_filter="login", status_filter="failed")) or 0
    creates = await db.scalar(build_scoped_query(action_filter="create")) or 0
    updates = await db.scalar(build_scoped_query(action_filter="update")) or 0
    deletes = await db.scalar(build_scoped_query(action_filter="delete")) or 0
    active_users = await db.scalar(build_scoped_query(unique_actors=True, status_filter="success")) or 0

    return {
        "total_logins_today": logins,
        "total_logouts_today": logouts,
        "total_failed_logins_today": failed_logins,
        "total_updates_today": updates,
        "total_deletes_today": deletes,
        "total_creates_today": creates,
        "active_users_today": active_users
    }


async def get_user_timeline(db: AsyncSession, current_user: Dict[str, Any], actor_type: str, actor_id: int) -> List[AuditLog]:
    """
    Fetch complete activity timeline for a Partner or Client ordered by date.
    """
    role = current_user["role"]
    user = current_user["user"]

    if role == UserRole.PARTNER:
        if actor_type == "partner" and actor_id != user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to view this partner's timeline")
        elif actor_type == "client":
            client_belongs = await db.scalar(
                select(func.count(Client.id))
                .where(Client.id == actor_id, Client.partner_id == user.id)
            )
            if client_belongs == 0:
                raise HTTPException(status_code=403, detail="You are not authorized to view this client's timeline")
        else:
            raise HTTPException(status_code=403, detail="Access denied")

    q = select(AuditLog).where(
        AuditLog.actor_type == actor_type,
        AuditLog.actor_id == actor_id
    ).order_by(AuditLog.created_at.desc())

    result = await db.execute(q)
    return result.scalars().all()


async def get_module_history(db: AsyncSession, current_user: Dict[str, Any], table_name: str, record_id: int) -> List[AuditLog]:
    """
    Fetch changelog list for a specific record.
    """
    q = select(AuditLog).where(
        AuditLog.table_name == table_name,
        AuditLog.record_id == record_id
    )

    role = current_user["role"]
    user = current_user["user"]

    if role == UserRole.PARTNER:
        client_ids_subquery = select(Client.id).where(Client.partner_id == user.id)
        scope_filter = or_(
            and_(AuditLog.actor_type == "partner", AuditLog.actor_id == user.id),
            and_(AuditLog.actor_type == "client", AuditLog.actor_id.in_(client_ids_subquery))
        )
        q = q.where(scope_filter)

    q = q.order_by(AuditLog.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()