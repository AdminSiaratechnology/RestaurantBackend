from fastapi import HTTPException
from sqlalchemy import select
from passlib.context import CryptContext

from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# =========================================================
# SUPER ADMIN
# =========================================================

async def create_superadmin_service(
    db,
    data
):
    result = await db.execute(
        select(SuperAdmin)
    )

    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            400,
            "Super Admin already exists"
        )

    admin = SuperAdmin(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(
            data.password
        ),
        role="super_admin",
        is_active=True
    )

    db.add(admin)

    await db.commit()
    await db.refresh(admin)

    return admin


async def get_superadmin_service(
    db
):
    result = await db.execute(
        select(SuperAdmin)
    )

    admin = result.scalars().first()

    if not admin:
        raise HTTPException(
            404,
            "Super Admin not found"
        )

    return admin


async def update_superadmin_service(
    db,
    data
):
    result = await db.execute(
        select(SuperAdmin)
    )

    admin = result.scalars().first()

    if not admin:
        raise HTTPException(
            404,
            "Super Admin not found"
        )

    if data.name:
        admin.name = data.name

    if data.email:
        admin.email = data.email

    if data.password:
        admin.password_hash = pwd_context.hash(
            data.password
        )

    if data.is_active is not None:
        admin.is_active = data.is_active

    await db.commit()
    await db.refresh(admin)

    return admin


# =========================================================
# PARTNERS
# =========================================================

async def create_partner_service(
    db,
    data
):
    result = await db.execute(
        select(Partner).where(
            Partner.email == data.email
        )
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Partner already exists"
        )

    partner = Partner(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(
            data.password
        ),
        role="partner",
        is_active=data.is_active
    )

    db.add(partner)

    await db.commit()
    await db.refresh(partner)

    return partner


async def update_partner_service(
    db,
    partner_id: int,
    data
):
    result = await db.execute(
        select(Partner).where(
            Partner.id == partner_id
        )
    )

    partner = result.scalar_one_or_none()

    if not partner:
        raise HTTPException(
            404,
            "Partner not found"
        )

    if data.name:
        partner.name = data.name

    if data.email:

        result = await db.execute(
            select(Partner).where(
                Partner.email == data.email,
                Partner.id != partner_id
            )
        )

        if result.scalar_one_or_none():
            raise HTTPException(
                400,
                "Email already exists"
            )

        partner.email = data.email

    if data.password:
        partner.password_hash = pwd_context.hash(
            data.password
        )

    if data.is_active is not None:
        partner.is_active = data.is_active

    await db.commit()
    await db.refresh(partner)

    return partner


async def get_all_partners_service(
    db,
    skip: int,
    limit: int
):
    result = await db.execute(
        select(Partner)
        .offset(skip)
        .limit(limit)
    )

    return result.scalars().all()


async def delete_partner_service(
    db,
    partner_id: int
):
    partner = await db.get(
        Partner,
        partner_id
    )

    if not partner:
        raise HTTPException(
            404,
            "Invalid partner_id"
        )

    partner.is_active = False

    await db.commit()
    await db.refresh(partner)

    return {
        "message":
        "Partner deactivated successfully"
    }


async def activate_partner_service(
    db,
    partner_id: int
):
    partner = await db.get(
        Partner,
        partner_id
    )

    if not partner:
        raise HTTPException(
            404,
            "Invalid partner_id"
        )

    if partner.is_active:
        raise HTTPException(
            400,
            "Partner already active"
        )

    partner.is_active = True

    await db.commit()
    await db.refresh(partner)

    return {
        "message":
        "Partner activated successfully"
    }