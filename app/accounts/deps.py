from fastapi import Depends, HTTPException, status, Request
from sqlalchemy import select
from app.db.config import SessionDep
from app.core.security import decode_token
from app.accounts.enum import UserRole
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.staff.model import Staff
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.accounts.brand.model import Brand
from app.accounts.permission.model import StaffPermission
from app.accounts.permission.services import CHEF_PERMISSIONS, WAITER_PERMISSIONS
from sqlalchemy.orm import selectinload
from app.accounts.staff.model import StaffRole
from app.core.cache import Cache


security = HTTPBearer()


async def get_current_user(
    db: SessionDep,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    # Check JWT Blacklist
    is_blacklisted = await Cache.get(f"blacklist:{token}")
    if is_blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    payload = decode_token(token)

    jti = payload.get("jti")
    if jti:
        is_blacklisted_jti = await Cache.get(f"blacklist:{jti}")
        if is_blacklisted_jti:
            raise HTTPException(status_code=401, detail="Token has been revoked")

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


async def get_client_if_accessible(client_id: int, db, current):
    client = await db.get(Client, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    role = current["role"]
    user = current["user"]

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        return client

    # ✅ PARTNER
    if role == UserRole.PARTNER:
        if client.partner_id != user.id:
            raise HTTPException(403, "Not allowed")
        return client

    # ✅ CLIENT
    if role == UserRole.CLIENT:
        if client.id != user.id:
            raise HTTPException(403, "Not allowed")
        return client

    # ✅ STAFF
    if role == UserRole.STAFF:
        if client.id != user.client_id:
            raise HTTPException(403, "Not allowed")
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





def require_staff_role(*allowed_roles: StaffRole):

    def checker(
        current=Depends(require_staff)
    ):

        staff = current["user"]

        if staff.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Allowed roles: {[r.value for r in allowed_roles]}"
            )

        return current

    return checker



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
    
    if role == UserRole.STAFF:
        if client.id != user.client_id:
            raise HTTPException(403, "Not allowed")
        return brand

    raise HTTPException(403, "Access denied")


access_one = require_roles(
    UserRole.CLIENT,
    UserRole.STAFF
)
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






def require_permission(permission_name: str, allow_client_admin: bool = True):

    async def checker(
        db: SessionDep,
        current=Depends(get_current_user)
    ):
        role = current["role"]

        # SuperAdmin, Partner, and Client bypass staff permission checks
        if allow_client_admin and role in (UserRole.SUPER_ADMIN, UserRole.PARTNER, UserRole.CLIENT):
            return current

        if role != UserRole.STAFF:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff access required"
            )

        user = current["user"]

        # If staff is chef or waiter, check standard role permission maps
        if getattr(user, "role", None) == StaffRole.chef:
            has_perm = CHEF_PERMISSIONS.get(permission_name, False)
            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{permission_name} permission denied"
                )
            return current

        if getattr(user, "role", None) == StaffRole.waiter:
            has_perm = WAITER_PERMISSIONS.get(permission_name, False)
            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{permission_name} permission denied"
                )
            return current

        # Manager: check cached or DB StaffPermission
        cache_key = f"permissions:user:{user.id}"
        permissions_dict = await Cache.get(cache_key)

        if not permissions_dict:
            result = await db.execute(
                select(StaffPermission).where(
                    StaffPermission.staff_id == user.id
                )
            )
            permissions = result.scalar_one_or_none()

            if not permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions assigned"
                )

            permissions_dict = {
                c.name: getattr(permissions, c.name)
                for c in permissions.__table__.columns
            }
            await Cache.set(cache_key, permissions_dict, expire=1800)

        has_permission = permissions_dict.get(permission_name, False)

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{permission_name} permission denied"
            )

        return current

    return checker


require_purchase_access = require_permission("manage_purchase", allow_client_admin=True)

