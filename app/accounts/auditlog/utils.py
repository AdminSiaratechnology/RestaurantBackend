from typing import Optional, Any, Dict, List
from datetime import datetime
from fastapi import Request

def model_to_dict(instance: Any, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convert a SQLAlchemy model instance into a serializable dictionary,
    excluding sensitive keys such as password hashes.
    """
    if instance is None:
        return {}
    if exclude is None:
        exclude = []

    sensitive_fields = {"password_hash", "hashed_password", "password", "secret", "token"}
    exclude_set = set(exclude).union(sensitive_fields)

    data = {}
    for column in instance.__table__.columns:
        if column.name in exclude_set:
            continue
        val = getattr(instance, column.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[column.name] = val
    return data

def get_client_ip(request: Request) -> Optional[str]:
    """
    Parse client IP address from request headers, respecting reverse proxies
    (like Nginx or Cloudflare) via X-Forwarded-For header.
    """
    if not request:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in the comma-separated chain is the client IP
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None