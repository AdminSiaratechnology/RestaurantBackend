from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

class AuditLogResponse(BaseModel):
    id: int
    actor_type: Optional[str] = None
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    module: Optional[str] = None
    table_name: Optional[str] = None
    record_id: Optional[int] = None
    description: Optional[str] = None
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    endpoint: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_records: int
    total_pages: int

class AuditLogListResponse(BaseModel):
    message: str
    data: List[AuditLogResponse]
    pagination: PaginationMeta

class AuditLogSummaryResponse(BaseModel):
    total_logins_today: int
    total_logouts_today: int
    total_failed_logins_today: int
    total_updates_today: int
    total_deletes_today: int
    total_creates_today: int
    active_users_today: int

class TimelineResponse(BaseModel):
    action: str
    performed_by: Optional[str] = None
    created_at: datetime

class HistoryResponse(BaseModel):
    id: int
    action: str
    performed_by: Optional[str] = None
    created_at: datetime