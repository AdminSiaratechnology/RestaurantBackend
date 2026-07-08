from typing import Any, List, Optional
from datetime import datetime
import math
from fastapi import APIRouter, Depends, Query, HTTPException

from app.db.config import SessionDep
from app.accounts.deps import require_roles
from app.accounts.enum import UserRole

from .schema import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogSummaryResponse,
    TimelineResponse,
    HistoryResponse
)
from .service import (
    get_paginated_logs,
    get_log_by_id,
    get_recent_logs,
    get_dashboard_summary,
    get_user_timeline,
    get_module_history
)

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"]
)

# Authentication dependency constraint
# Blocks Clients and Staff from viewing audit logs; only allows Super Admin & Partner.
audit_log_access = require_roles(UserRole.SUPER_ADMIN, UserRole.PARTNER)

@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    db: SessionDep,
    current_user=Depends(audit_log_access),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (partner/client/super_admin/system)"),
    actor_id: Optional[int] = Query(None, description="Filter by actor ID"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    module: Optional[str] = Query(None, description="Filter by module"),
    table_name: Optional[str] = Query(None, description="Filter by affected table"),
    record_id: Optional[int] = Query(None, description="Filter by affected record ID"),
    status: Optional[str] = Query(None, description="Filter by status (success/failed)"),
    from_date: Optional[datetime] = Query(None, description="Filter by from date"),
    to_date: Optional[datetime] = Query(None, description="Filter by to date"),
    sort: str = Query("newest", regex="^(newest|oldest)$", description="Sort order: newest or oldest")
) -> Any:
    """
    List audit logs matching search filters with pagination and scoping.
    """
    logs, total = await get_paginated_logs(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        module=module,
        table_name=table_name,
        record_id=record_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        sort=sort
    )
    total_pages = math.ceil(total / page_size) if page_size else 1
    return {
        "message": "Audit logs fetched successfully",
        "data": logs,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total,
            "total_pages": total_pages
        }
    }

@router.get("/recent", response_model=List[AuditLogResponse])
async def get_recent_activities(
    db: SessionDep,
    current_user=Depends(audit_log_access),
    limit: int = Query(20, ge=1, le=100, description="Limit count")
) -> Any:
    """
    Get the latest 20 activities performed across the system.
    """
    return await get_recent_logs(db=db, current_user=current_user, limit=limit)

@router.get("/summary", response_model=AuditLogSummaryResponse)
async def get_dashboard_activity_summary(
    db: SessionDep,
    current_user=Depends(audit_log_access)
) -> Any:
    """
    Retrieve audit statistics summary for today (logins, logouts, creates, updates, deletes, active users).
    """
    return await get_dashboard_summary(db=db, current_user=current_user)

@router.get("/timeline/{actor_type}/{actor_id}", response_model=List[TimelineResponse])
async def get_actor_timeline(
    actor_type: str,
    actor_id: int,
    db: SessionDep,
    current_user=Depends(audit_log_access)
) -> Any:
    """
    Get activity history timeline for a specific Partner or Client.
    """
    logs = await get_user_timeline(
        db=db,
        current_user=current_user,
        actor_type=actor_type,
        actor_id=actor_id
    )
    # Map to schema structure (action, performed_by, created_at)
    return [
        {
            "action": log.action,
            "performed_by": log.actor_name or log.actor_email or "System",
            "created_at": log.created_at
        } for log in logs
    ]

@router.get("/module/{table_name}/{record_id}", response_model=List[HistoryResponse])
async def get_record_changelog(
    table_name: str,
    record_id: int,
    db: SessionDep,
    current_user=Depends(audit_log_access)
) -> Any:
    """
    Retrieve change history list for a specific record.
    """
    logs = await get_module_history(
        db=db,
        current_user=current_user,
        table_name=table_name,
        record_id=record_id
    )
    return [
        {
            "id": log.id,
            "action": log.action,
            "performed_by": log.actor_name or log.actor_email or "System",
            "created_at": log.created_at
        } for log in logs
    ]

@router.get("/{id}", response_model=AuditLogResponse)
async def read_audit_log_detail(
    id: int,
    db: SessionDep,
    current_user=Depends(audit_log_access)
) -> Any:
    """
    Retrieve specific audit log details (includes old_data and new_data values).
    """
    log = await get_log_by_id(db=db, current_user=current_user, log_id=id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return log