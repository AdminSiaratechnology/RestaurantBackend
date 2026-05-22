from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.pricing.schema import PricingCreate, PricingUpdate, PricingOut
from app.accounts.deps import access_four, UserRole, require_client, get_client_if_accessible

router = APIRouter(prefix="/pricing", tags=["Pricing"])

# from app.db.base import Base
# from app.db.config import engine

# async def init_db():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

# ✅ CREATE PRICING
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

    if existing_pricing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="Price already exists for this item"
        )

    # ✅ Create pricing
    pricing = Pricing(
        client_id=client.id,
        branch_id=data.branch_id,
        item_id=data.item_id,
        price=data.price,
        cost_price=data.cost_price,
        discount=data.discount,
        tax_rate=data.tax_rate,
        calories=data.calories,
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
    branch_id: int | None = None,
    item_id: int | None = None,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.CLIENT:
        client_id = user.id
    elif role == UserRole.STAFF:
        client_id = user.client_id
        if branch_id is None:
            branch_id = user.branch_id
    else:
        raise HTTPException(400, "Client context not found for this role")

    query = select(Pricing).where(Pricing.client_id == client_id)

    if branch_id is not None:
        query = query.where(Pricing.branch_id == branch_id)

    if item_id is not None:
        query = query.where(Pricing.item_id == item_id)

    result = await db.execute(query)

    return result.scalars().all()



# ✅ UPDATE PRICING
# ✅ UPDATE PRICING
@router.put("/update_pricing/{pricing_id}", response_model=PricingOut)
async def update_pricing(
    pricing_id: int,
    data: PricingUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    result = await db.execute(
        select(Pricing).where(Pricing.id == pricing_id)
    )

    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(404, "Pricing not found")

    await get_client_if_accessible(
        client_id=pricing.client_id,
        db=db,
        current=current
    )

    # ✅ MARKED POINTS
    if data.price is not None:
        pricing.price = data.price

    if data.cost_price is not None:
        pricing.cost_price = data.cost_price

    if data.discount is not None:
        pricing.discount = data.discount

    if data.tax_rate is not None:
        pricing.tax_rate = data.tax_rate

    if data.calories is not None:
        pricing.calories = data.calories

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
    current=Depends(access_four)
):
    result = await db.execute(
        select(Pricing).where(Pricing.id == pricing_id)
    )

    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(404, "Pricing not found")

    await get_client_if_accessible(
        client_id=pricing.client_id,
        db=db,
        current=current
    )

    await db.delete(pricing)

    await db.commit()

    return {
        "message": "Pricing deleted successfully"
    }