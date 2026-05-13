from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from app.accounts.deps import require_super_admin
from app.db.config import SessionDep
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.superadmin.schemas import (
    SuperAdminCreate,
    SuperAdminOut,
    SuperAdminUpdate,
    PartnerCreate,
    PartnerOut,
)




router = APIRouter(
    prefix="/superadmin",
    tags=["Super Admin"]
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ✅ CREATE SUPER ADMIN (ONLY ONCE - PUBLIC)
@router.post("/create", response_model=SuperAdminOut)
async def create_superadmin(data: SuperAdminCreate, db: SessionDep):
    result = await db.execute(select(SuperAdmin))
    existing = result.scalars().first()

    if existing:
        raise HTTPException(400, "Super Admin already exists")

    admin = SuperAdmin(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        role="super_admin",
        is_active=True
    )

    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    return admin


# ✅ GET SUPER ADMIN
@router.get("/", response_model=SuperAdminOut)
async def get_superadmin(
    db: SessionDep,
    current=Depends(require_super_admin)
):
    result = await db.execute(select(SuperAdmin))
    admin = result.scalars().first()

    if not admin:
        raise HTTPException(404, "Super Admin not found")

    return admin


# ✅ UPDATE SUPER ADMIN
@router.put("/update", response_model=SuperAdminOut)
async def update_superadmin(
    data: SuperAdminUpdate,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    result = await db.execute(select(SuperAdmin))
    admin = result.scalars().first()

    if not admin:
        raise HTTPException(404, "Super Admin not found")

    if data.name:
        admin.name = data.name

    if data.email:
        admin.email = data.email

    if data.password:
        admin.password_hash = pwd_context.hash(data.password)

    if data.is_active is not None:
        admin.is_active = data.is_active

    await db.commit()
    await db.refresh(admin)

    return admin




@router.post("/partners", response_model=PartnerOut)
async def create_partner(
    data: PartnerCreate,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    result = await db.execute(
        select(Partner).where(Partner.email == data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Partner already exists")

    partner = Partner(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        role="partner",  # 🔥 FIXED (lowercase)
        is_active=data.is_active
    )

    db.add(partner)
    await db.commit()
    await db.refresh(partner)

    return partner




@router.put("/partners/{partner_id}", response_model=PartnerOut)
async def update_partner(
    partner_id: int,
    data: PartnerCreate,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    result = await db.execute(
        select(Partner).where(Partner.id == partner_id)
    )
    partner = result.scalar_one_or_none()

    if not partner:
        raise HTTPException(404, "Partner not found")

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
            raise HTTPException(400, "Email already exists")

        partner.email = data.email

    if data.password:
        partner.password_hash = pwd_context.hash(data.password)

    if data.is_active is not None:
        partner.is_active = data.is_active

    await db.commit()
    await db.refresh(partner)

    return partner





@router.get("/partners", response_model=list[PartnerOut])
async def get_all_partners(
    db: SessionDep,
    current=Depends(require_super_admin),
    skip: int = 0,
    limit: int = 10
):
    result = await db.execute(
        select(Partner).offset(skip).limit(limit)
    )
    return result.scalars().all()



@router.delete("/partners/{partner_id}")
async def delete_partner(
    partner_id: int,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    partner = await db.get(Partner, partner_id)

    if not partner:
        raise HTTPException(status_code=404, detail="Invalid partner_id")

    # ✅ Soft delete (deactivate)
    partner.is_active = False

    await db.commit()
    await db.refresh(partner)

    return {"message": "Partner deactivated successfully"}

@router.put("/partners/{partner_id}/activate")
async def activate_partner(
    partner_id: int,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    partner = await db.get(Partner, partner_id)

    if not partner:
        raise HTTPException(status_code=404, detail="Invalid partner_id")

    # already active check
    if partner.is_active:
        raise HTTPException(status_code=400, detail="Partner already active")

    # ✅ Activate
    partner.is_active = True

    await db.commit()
    await db.refresh(partner)

    return {"message": "Partner activated successfully"}