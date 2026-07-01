
from fastapi import APIRouter, Response, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.accounts.auth.model import authenticate_user
from app.accounts.auth.schemas import LoginRequest, ChangePasswordRequest
from app.accounts.auth.utils import verify_password, hash_password
from app.db.config import SessionDep
from app.accounts.enum import UserRole
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.staff.model import Staff
from app.core.settings import settings

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("user_id")
        role = payload.get("role")
        if user_id is None or role is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return {"user_id": user_id, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

async def find_user_by_id_and_role(user_id: int, role: str, db):
    model_map = {
        UserRole.SUPER_ADMIN.value: SuperAdmin,
        UserRole.PARTNER.value: Partner,
        UserRole.CLIENT.value: Client,
        UserRole.STAFF.value: Staff,
    }
    
    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=404, detail="User role not found")
        
    from sqlalchemy import select
    result = await db.execute(select(model).where(model.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ✅ Super Admin Portal
@router.post("/login/partner")
async def super_admin_login(
    data: LoginRequest,
    db: SessionDep,
    request: Request,
):
    return await authenticate_user(
        data=data,
        db=db,
        request=request,
        response=None,
        allowed_roles=[
            UserRole.SUPER_ADMIN,
            UserRole.PARTNER
        ]
    )


# ✅ Client Portal
@router.post("/login/staff")
async def client_login(
    data: LoginRequest,
    db: SessionDep,
    request: Request,
):
    return await authenticate_user(
        data=data,
        db=db,
        request=request,
        response=None,
        allowed_roles=[
            UserRole.CLIENT,
            UserRole.STAFF
        ]
    )

# ✅ Change Password
@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    db: SessionDep,
    current_user: dict = Depends(get_current_user),
):
    user = await find_user_by_id_and_role(
        current_user["user_id"],
        current_user["role"],
        db
    )
    
    # Verify current password
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
        
    # Update to new password
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    
    return {"message": "Password changed successfully"}

from app.core.cache import Cache
import time

@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    expire = 86400
    jti = None
    # Try to decode to get user_id to clear active session and get remaining TTL
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("user_id")
        jti = payload.get("jti")
        exp = payload.get("exp")
        if exp:
            remaining = int(exp - time.time())
            if remaining > 0:
                expire = remaining
        if user_id:
            await Cache.delete(f"session:user:{user_id}")
    except JWTError:
        pass

    if jti:
        await Cache.set(f"blacklist:{jti}", "true", expire=expire)
    else:
        await Cache.set(f"blacklist:{token}", "true", expire=expire)

    return {"message": "Successfully logged out"}