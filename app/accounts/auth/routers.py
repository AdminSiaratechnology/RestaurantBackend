# from fastapi import APIRouter, HTTPException, Response
# from httpx import request
# from sqlalchemy import select
# from app.db.config import SessionDep
# from app.accounts.models import User
# from app.accounts.schemas import LoginRequest
# from app.accounts.utils import verify_password, create_access_token
# from app.utils.audit import log_action

# router = APIRouter(prefix="/auth",tags=["Auth"])


# @router.post("/login")
# async def login(data: LoginRequest, db: SessionDep, response: Response):

#     # ✅ Find user from single table
#     stmt = select(User).where(User.email == data.email)
#     result = await db.scalars(stmt)
#     user = result.first()

#     if not user:
#         raise HTTPException(status_code=401, detail="Invalid email or password")

#     # ✅ Verify password
#     if not verify_password(data.password, user.password_hash):
#         raise HTTPException(status_code=401, detail="Invalid email or password")

#     # ✅ Create access + refresh tokens
#     tokens = await create_access_token(db, user)

#     # ✅ Store tokens in cookies (secure way)
#     response.set_cookie(
#         key="access_token",
#         value=tokens["access_token"],
#         httponly=True,
#         secure=False,  # 🔥 True in production
#         samesite="lax"
#     )

#     response.set_cookie(
#         key="refresh_token",
#         value=tokens["refresh_token"],
#         httponly=True,
#         secure=False,
#         samesite="lax"
#     )

#     await log_action(
#         db,
#         table_name="auth",
#         action="LOGIN",
#         record_id=user.id,
#         changed_by=user.id,
#         new_data={"email": user.email},
#         request=request,
#     )

#     return {
#         "message": "Login successful",
#         "token_type": "bearer",
#         "role": user.role,
#         "user": {
#         "id": user.id,
#         "email": user.email,
#         "tenant_id": user.tenant_id
#     }
#     }
from fastapi import APIRouter, Response
from app.accounts.auth.model import authenticate_user
from app.accounts.auth.schemas import LoginRequest
from app.db.config import SessionDep
from app.accounts.enum import UserRole

router = APIRouter(prefix="/auth", tags=["Auth"])


# ✅ Super Admin Portal
@router.post("/login/partner")
async def super_admin_login(
    data: LoginRequest,
    db: SessionDep,
):
    return await authenticate_user(
        data=data,
        db=db,
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
):
    return await authenticate_user(
        data=data,
        db=db,
        response=None,
        allowed_roles=[
            UserRole.CLIENT,
            UserRole.STAFF
        ]
    )