from fastapi import HTTPException
from sqlalchemy import select
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.staff.model import Staff
from app.accounts.auth.utils import verify_password, create_access_token
from app.accounts.enum import UserRole


async def authenticate_user(data, db, response, allowed_roles: list):
    email = data.email

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
        raise HTTPException(401, "Invalid email or password")

    # 🔐 Password check
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    # 🔐 Role restriction
    if role not in allowed_roles:
        raise HTTPException(403, "Access denied for this portal")

    # ✅ Create token payload
    token_data = {
        "user_id": user.id,
        "role": role.value
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

    return {
        "access_token": access_token,
        "role": role.value,
        "user": user_payload
    }