from fastapi import Depends, HTTPException, status, Request
from sqlalchemy import select
from app.accounts import role
from app.db.config import SessionDep
from app.core.security import decode_token
from app.accounts.enum import UserRole
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.staff.model import Staff
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials



security = HTTPBearer()


async def get_current_user(
    db: SessionDep,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    payload = decode_token(token)

    user_id = payload.get("user_id")
    role_str = payload.get("role")

    if not user_id or not role_str:
        raise HTTPException(401, "Invalid token")

    # ✅ FIX: convert string → enum
    try:
        role = UserRole(role_str)
    except ValueError:
        raise HTTPException(401, "Invalid role in token")

    model_map = {
        UserRole.SUPER_ADMIN: SuperAdmin,
        UserRole.PARTNER: Partner,
        UserRole.CLIENT: Client,
        UserRole.STAFF: Staff,
    }

    model = model_map.get(role)

    user = await db.get(model, int(user_id))

    if not user:
        raise HTTPException(401, "User not found")

    return {
        "user": user,
        "role": role
    }



def require_super_admin(current=Depends(get_current_user)):
    if current["role"] != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required"
        )
    return current


def require_partner(current=Depends(get_current_user)):
    if current["role"] != UserRole.PARTNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Partner access required"
        )
    return current


def require_client(current=Depends(get_current_user)):
    if current["role"] != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client access required"
        )
    return current


def require_staff(current=Depends(get_current_user)):
    if current["role"] != UserRole.STAFF:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )
    return current

def require_roles(*allowed_roles: UserRole):
    def role_checker(current=Depends(get_current_user)):
        if current["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current
    return role_checker


from app.accounts.client.model import Client


async def get_client_if_accessible(client_id: int, db, current):
    client = await db.get(Client, client_id)

    if not client:
        raise HTTPException(404, "Client     not found")

    role = current["role"]
    user = current["user"]

    if role == UserRole.SUPER_ADMIN:
        return client

    if role == UserRole.PARTNER:
        if client.partner_id != user.id:
            raise HTTPException(403, "Not allowed to access this client")
        return client

    if role == UserRole.CLIENT:
        if client.id != user.id:
            raise HTTPException(403, "Not allowed to access this client")
        return client

    raise HTTPException(403, "Access denied")


async def client_access_dependency(
    client_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):
    return await get_client_if_accessible(
        client_id=client_id,
        db=db,
        current=current
    )


from app.accounts.brand.model import Brand


from sqlalchemy import select
from sqlalchemy.orm import selectinload

# async def get_brand_if_accessible(
#     brand_id: int,
#     db: SessionDep,
#     current=Depends(get_current_user)
# ):
#     user = current["user"]

#     result = await db.execute(
#         select(Brand)
#         .options(selectinload(Brand.client))  # ✅ only this
#         .where(Brand.id == brand_id)
#     )

#     brand = result.scalar_one_or_none()

#     if not brand:
#         raise HTTPException(404, "Brand not found")

#     client = brand.client

#     if role == UserRole.SUPER_ADMIN:
#         return brand

#     if role == UserRole.PARTNER:
#         if client.partner_id != user.id:
#             raise HTTPException(403, "Not allowed")
#         return brand

#     if role == UserRole.CLIENT:
#         # ✅ FIX
#         if client.id != user.id:
#             raise HTTPException(403, "Not allowed")
#         return brand

#     raise HTTPException(403, "Access denied")
#     # if not brand:
#     #     raise HTTPException(404, "Brand not found")

#     # client = brand.client

#     # # ✅ SAFE now (no lazy loading)
#     # if client.client_id != user.id:
#     #     raise HTTPException(403, "Not allowed")

#     # return brand

async def get_brand_if_accessible(
    brand_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):
    role = current["role"]
    user = current["user"]

    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.client))
        .where(Brand.id == brand_id)
    )

    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(404, "Brand not found")

    client = brand.client

    if role == UserRole.SUPER_ADMIN:
        return brand

    if role == UserRole.PARTNER:
        if client.partner_id != user.id:
            raise HTTPException(403, "Not allowed")
        return brand

    if role == UserRole.CLIENT:
        if client.id != user.id:
            raise HTTPException(403, "Not allowed")
        return brand

    raise HTTPException(403, "Access denied")



access_one = require_roles(UserRole.CLIENT)
access_two = require_roles(UserRole.SUPER_ADMIN, UserRole.PARTNER)
access_four = require_roles(UserRole.SUPER_ADMIN, UserRole.PARTNER, UserRole.CLIENT, UserRole.STAFF)
access_three = require_roles(UserRole.SUPER_ADMIN, UserRole.PARTNER, UserRole.CLIENT)



def calculate_status(stock_qty, reorder_level): 
    if stock_qty <= 0:
        return "out_of_stock"
    elif stock_qty <= reorder_level:
        return "low_stock"
    return "in_stock"





client_access = require_roles(UserRole.PARTNER, UserRole.SUPER_ADMIN)