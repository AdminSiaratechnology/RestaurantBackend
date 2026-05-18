from app.accounts.client.model import Client

from sqlalchemy import select
from passlib.context import CryptContext
from app.accounts.partner.model import Partner
from app.accounts.staff.model import Staff
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.deps import UserRole
from app.core.security import create_access_token   # ✅ FIXED IMPORT

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def authenticate_user(db, email: str, password: str):
    models = [
        (SuperAdmin, UserRole.SUPER_ADMIN),
        (Partner, UserRole.PARTNER),
        (Client, UserRole.CLIENT),
        (Staff, UserRole.STAFF),
    ]

    for model, role in models:
        result = await db.execute(
            select(model).where(model.email == email)
        )
        user = result.scalar_one_or_none()

        if user:
            # ❌ Wrong password
            if not pwd_context.verify(password, user.password_hash):
                return None

            # ✅ Build token payload
            payload = {
                "user_id": user.id,
                "role": role.value,  # ✅ ALWAYS STRING
                "tenant_id": getattr(user, "tenant_id", None),
                "admin_id": getattr(user, "admin_id", None),   # 🔥 IMPORTANT ADD
                "partner_id": getattr(user, "partner_id", None) # 🔥 IMPORTANT ADD
            }

            token = create_access_token(payload)

            return {
                "access_token": token,
                "token_type": "bearer",
                "role": role.value
            }

    return None