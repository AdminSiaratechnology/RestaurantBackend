from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from slugify import slugify
from app.accounts.deps import access_three,UserRole
from app.db.config import SessionDep
from app.accounts.brand.model import Brand
from app.accounts.brand.schema import BrandCreate, BrandOut, BrandUpdate
from app.accounts.client.model import Client

from app.accounts.deps import (
    get_brand_if_accessible,
    get_client_if_accessible
)

router = APIRouter(prefix="/brand", tags=["Brand"])


# ✅ CREATE BRAND
@router.post("/post", response_model=BrandOut)
async def create_brand(
    data: BrandCreate,
    db: SessionDep,
    current=Depends(access_three)
):
    role = UserRole(current["role"])
    user = current["user"]

    client = await get_client_if_accessible(
        client_id=data.client_id,
        db=db,
        current=current
    )

    slug = slugify(data.slug)

    # ✅ No lazy load issue here
    result = await db.execute(
        select(Brand).where(
            Brand.slug == slug,
            Brand.client_id == client.id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Brand slug already exists in this client")

    brand = Brand(
        name=data.name,
        slug=slug,
        client_id=client.id
    )

    db.add(brand)
    await db.commit()
    await db.refresh(brand)

    return brand


# ✅ GET ALL BRANDS (FIXED)
@router.get("/all_brand", response_model=list[BrandOut])
async def get_brands(
    db: SessionDep,
    current=Depends(access_three)
):
    role = UserRole(current["role"])
    user = current["user"]

    if role == UserRole.SUPER_ADMIN:
        query = select(Brand)

    elif role == UserRole.PARTNER:
        query = (
            select(Brand)
            .join(Brand.client)       
            .where(Client.partner_id == user.id)
        )

    elif role == UserRole.CLIENT:
        query = (
            select(Brand)
            .join(Brand.client)
            .where(Client.id == user.id)
        )

    else:
        raise HTTPException(403, "Not allowed")

    result = await db.execute(
        query.options(
            selectinload(Brand.client)   # ✅ preload client            
        )
    )

    return result.scalars().all()


# # ✅ GET SINGLE BRAND (already safe if dependency fixed)
# @router.get("/{brand_id}", response_model=BrandOut)
# async def get_brand(
#     brand: Brand = Depends(get_brand_if_accessible),
#     current=Depends(access_three)
# ):
#     return brand


# ✅ UPDATE BRAND (FIXED)
@router.put("/update/{brand_id}", response_model=BrandOut)
async def update_brand(
    brand_id: int,
    data: BrandUpdate,
    db: SessionDep,
    current=Depends(access_three)
):
    role = UserRole(current["role"])
    user = current["user"]

    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.client))  # ✅ preload client
        .where(Brand.id == brand_id)
    )
    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(404, "Brand not found")

    await get_client_if_accessible(
        db, brand.client_id, role, user
    )

    if data.name:
        brand.name = data.name

    if data.slug:
        slug = slugify(data.slug)

        result = await db.execute(
            select(Brand).where(
                Brand.slug == slug,
                Brand.client_id == brand.client_id,
                Brand.id != brand_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(400, "Slug already exists")

        brand.slug = slug

    await db.commit()
    await db.refresh(brand)

    return brand


# ✅ DELETE BRAND (FIXED)
@router.delete("/delete/{brand_id}")
async def delete_brand(
    brand_id: int,
    db: SessionDep,
    current=Depends(access_three)
):
    role = UserRole(current["role"])
    user = current["user"]

    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.client))  # ✅ preload client
        .where(Brand.id == brand_id)
    )
    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(404, "Brand not found")

    await get_client_if_accessible(
        db, brand.client_id, role, user
    )

    await db.delete(brand)
    await db.commit()

    return {"message": "Brand deleted"}