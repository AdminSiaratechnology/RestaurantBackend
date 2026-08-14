from fastapi import HTTPException
from sqlalchemy import select
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.staff.model import Staff
from app.accounts.auth.utils import verify_password, create_access_token
from app.accounts.enum import UserRole
from app.core.cache import Cache
from app.core.redis import redis_client
from app.accounts.auditlog.service import create_audit_log
import time
import json
from uuid import uuid4
from datetime import datetime

# Maps role value → DB table name for audit log
_ROLE_TABLE_MAP = {
    "super_admin": "superadmins",
    "partner":     "partners",
    "client":      "clients",
    "staff":       "staffs",
}


async def authenticate_user(data, db, request, response, allowed_roles: list):
    email = data.email

    # IP Rate Limiting
    client_ip = request.client.host if request and request.client else "unknown"
    rate_limit_key = f"login:{client_ip}"
    
    # attempts = await redis_client.get(rate_limit_key)
    # if attempts and int(attempts) >= 5:
    #     raise HTTPException(429, "Too many login attempts. Please try again later.")

    # 🔍 Search user in all tables
    user = None
    role = None

    model_map = [
        (SuperAdmin, UserRole.SUPER_ADMIN),
        (Partner, UserRole.PARTNER),
        (Client, UserRole.CLIENT),
        (Staff, UserRole.STAFF),
    ]

    for model, model_role in model_map:
        result = await db.execute(
            select(model).where(model.email == email)
        )
        obj = result.scalar_one_or_none()

        if obj:
            user = obj
            role = model_role
            break

    if not user:
        # Increment failed attempts
        await redis_client.incr(rate_limit_key)
        await redis_client.expire(rate_limit_key, 900) # 15 mins
        raise HTTPException(401, "Invalid email or password")

    # 🔐 Password check
    if not verify_password(data.password, user.password_hash):
        await redis_client.incr(rate_limit_key)
        await redis_client.expire(rate_limit_key, 900)
        raise HTTPException(401, "Invalid email or password")

    # 🔐 Role restriction
    if role not in allowed_roles:
        raise HTTPException(403, "Access denied for this portal")

    # ✅ Create token payload
    jti = str(uuid4())
    token_data = {
        "user_id": user.id,
        "role": role.value,
        "jti": jti
    }

    access_token = create_access_token(token_data)

    user_payload = {
        "id": user.id,
        "email": user.email
    }
    if role == UserRole.STAFF:
        user_payload["client_id"] = user.client_id
        user_payload["branch_id"] = user.branch_id
        user_payload["role"] = user.role
    elif role == UserRole.CLIENT:
        user_payload["client_id"] = user.id

    # Clear login attempts on success
    await redis_client.delete(rate_limit_key)

    # Store active session in Redis
    session_data = {
        "login_time": time.time(),
        "device": request.headers.get("user-agent", "Unknown"),
        "role": role.value,
        "jwt_id": jti
    }
    await Cache.set(f"session:user:{user.id}", session_data, expire=86400)

    # ✅ Audit Log: Record login event
    login_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    await create_audit_log(
        db=db,
        actor=user,
        action="login",
        module="Auth",
        table_name=_ROLE_TABLE_MAP.get(role.value, role.value),
        record_id=user.id,
        description=f"{role.value.replace('_', ' ').title()} '{getattr(user, 'name', user.email)}' logged in at {login_time_str}.",
        status="success",
        request=request,
    )

    return {
        "access_token": access_token,
        "role": role.value,
        "user": user_payload
    }