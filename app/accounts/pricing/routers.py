from multiprocessing.dummy.connection import Client

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.config import SessionDep
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.pricing.schema import PricingCreate, PricingUpdate, PricingOut
from app.accounts.deps import access_three,UserRole
from app.accounts.deps import require_super_admin, require_client, require_staff
from app.models import order

router = APIRouter(prefix="/pricing", tags=["Pricing"])

from app.db.base import Base
from app.db.config import engine

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ✅ CREATE PRICING
@router.post("/set_pricing", response_model=PricingOut)
async def create_pricing(
    data: PricingCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    # ✅ Validate item belongs to logged-in client
    result = await db.execute(
        select(Item).where(
            Item.id == data.item_id,
            Item.client_id == client.id
        )
    )

    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(404, "Item not found")

    # ✅ CHECK IF PRICING ALREADY EXISTS
    existing_pricing = await db.execute(
        select(Pricing).where(
            Pricing.item_id == data.item_id,
            Pricing.client_id == client.id
        )
    )

    if existing_pricing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Price already exists for this item"
        )

    # ✅ Create pricing
    pricing = Pricing(
        client_id=client.id,
        item_id=data.item_id,
        price=data.price,
        is_active=True
    )

    db.add(pricing)

    await db.commit()
    await db.refresh(pricing)

    return pricing



# ✅ GET ALL PRICING
@router.get("/get_pricings", response_model=list[PricingOut])
async def get_pricings(
    db: SessionDep,
    current=Depends(access_three)
):
    client = current["user"]

    result = await db.execute(
        select(Pricing).where(
            Pricing.client_id == client.id
        )
    )

    return result.scalars().all()



# ✅ UPDATE PRICING
@router.put("/update_pricing/{pricing_id}", response_model=PricingOut)
async def update_pricing(
    pricing_id: int,
    data: PricingUpdate,
    db: SessionDep,
    current=Depends(access_three)
):
    client = current["user"]

    result = await db.execute(
        select(Pricing).where(
            Pricing.id == pricing_id,
            Pricing.client_id == client.id
        )
    )

    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(404, "Pricing not found")

    if data.price is not None:
        pricing.price = data.price

    if data.is_active is not None:
        pricing.is_active = data.is_active

    await db.commit()
    await db.refresh(pricing)

    return pricing




# ✅ DELETE PRICING
@router.delete("/delete_pricing/{pricing_id}")
async def delete_pricing(
    pricing_id: int,
    db: SessionDep,
    current=Depends(access_three)
):
    client = current["user"]

    result = await db.execute(
        select(Pricing).where(
            Pricing.id == pricing_id,
            Pricing.client_id == client.id
        )
    )

    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(404, "Pricing not found")

    await db.delete(pricing)

    await db.commit()

    return {
        "message": "Pricing deleted successfully"
    }