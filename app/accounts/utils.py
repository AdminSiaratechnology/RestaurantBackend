from app.accounts.brand.model import Brand
from app.accounts.models import User
from app.accounts.enum import UserRole
from fastapi import Depends, HTTPException, status
from app.accounts.deps import get_current_user
from app.core.security import decode_token
from app.models.platform import client
from app.db.config import SessionDep    


def require_roles(*allowed_roles: UserRole):

    def checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        return user

    return checker


# ✅ Shortcuts
require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_partner = require_roles(UserRole.PARTNER)
require_client = require_roles(UserRole.CLIENT)
require_staff = require_roles(UserRole.STAFF)


from fastapi import Depends, HTTPException
from sqlalchemy import select

from app.accounts.client.model import Client
from app.db.config import SessionDep
from app.models import user

async def get_client_if_accessible(
    db: SessionDep,
    client_id: int,
    user: User
):
    stmt = select(Client).where(Client.id == client_id)
    result = await db.scalars(stmt)
    client = result.first()

    if not client:
        raise HTTPException(404, "Client not found")

    # 🔒 Access rules
    if user.role == UserRole.CLIENT and client.id != user.id:
        raise HTTPException(403, "Not your client")

    if user.role == UserRole.STAFF and client.id != user.client_id:
        raise HTTPException(403, "Not your client")

    if user.role == UserRole.PARTNER:
        if client.partner_id != user.partner_id:
            raise HTTPException(403, "Not your client")

    return client





async def get_brand_if_accessible(
    db: SessionDep,
    brand_id: int,
    user: user
):
    stmt = select(Brand).where(Brand.id == brand_id)
    result = await db.scalars(stmt)
    brand = result.first()

    if not brand:
        raise HTTPException(404, "Brand not found")

    await get_client_if_accessible(
        db, brand.client_id, user
    )

    return brand