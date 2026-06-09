# =========================================================
# app/accounts/pricing/routers.py
# =========================================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.client.model import Client
from app.accounts.branch.model import Branch
from app.db.config import SessionDep
from app.accounts.pricing.schema import (
    PricingCreate,
    PricingUpdate,
    PricingOut
)
from app.accounts.pricing.model import PricingTaxHistory
from app.accounts.pricing.schema import TaxHistoryOut

from app.accounts.deps import (
    access_four,
    UserRole,
    require_client,
    get_client_if_accessible
)

router = APIRouter(
    prefix="/pricing",
    tags=["Pricing"]
)


# =========================================================
# CREATE PRICING
# =========================================================

@router.post(
    "/set_pricing",
    response_model=PricingOut
)
async def create_pricing(
    data: PricingCreate,
    db: SessionDep,
    current=Depends(require_client)
):

    client = current["user"]

    # =====================================================
    # VALIDATE ITEM
    # =====================================================

    result = await db.execute(
        select(Item).where(
            Item.id == data.item_id,
            Item.client_id == client.id
        )
    )

    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            404,
            "Item not found"
        )

    if item.branch_id != data.branch_id:
        raise HTTPException(
            400,
            "branch_id must match the item's branch"
        )

    # =====================================================
    # UPSERT (per item + branch — safe after POST /items/)
    # =====================================================

    existing_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == data.item_id,
            Pricing.client_id == client.id,
            Pricing.branch_id == data.branch_id,
        )
    )

    pricing = existing_result.scalar_one_or_none()

    if pricing:
        pricing.price = data.price
        pricing.cost_price = data.cost_price
        pricing.discount = data.discount
        pricing.tax = data.tax
        pricing.cgst_rate = data.tax / 2
        pricing.sgst_rate = data.tax / 2
        pricing.calories = data.calories
        pricing.is_active = data.is_active
    else:
        pricing = Pricing(
            client_id=client.id,
            branch_id=data.branch_id,
            item_id=data.item_id,
            price=data.price,
            cost_price=data.cost_price,
            discount=data.discount,
            tax=data.tax,
            cgst_rate=data.tax / 2,
            sgst_rate=data.tax / 2,
            calories=data.calories,
            is_active=data.is_active,
        )
        db.add(pricing)

    await db.commit()

    await db.refresh(pricing)

    return pricing


# =========================================================
# GET ALL PRICINGS
# =========================================================

@router.get(
    "/get_pricings",
    response_model=list[PricingOut]
)
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
        raise HTTPException(
            400,
            "Client context not found"
        )

    query = select(Pricing).where(
        Pricing.client_id == client_id
    )

    if branch_id is not None:
        query = query.where(
            Pricing.branch_id == branch_id
        )

    if item_id is not None:
        query = query.where(
            Pricing.item_id == item_id
        )

    result = await db.execute(query)

    return result.scalars().all()


# =========================================================
# UPDATE PRICING
# =========================================================

@router.put(
    "/update_pricing/{pricing_id}",
    response_model=PricingOut
)
async def update_pricing(
    pricing_id: int,
    data: PricingUpdate,
    db: SessionDep,
    current=Depends(access_four)
):

    result = await db.execute(
        select(Pricing).where(
            Pricing.id == pricing_id
        )
    )

    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(
            404,
            "Pricing not found"
        )

    await get_client_if_accessible(
        client_id=pricing.client_id,
        db=db,
        current=current
    )

    # =====================================================
    # UPDATE FIELDS
    # =====================================================

    if data.price is not None:
        pricing.price = data.price

    if data.cost_price is not None:
        pricing.cost_price = data.cost_price

    if data.discount is not None:
        pricing.discount = data.discount

    if data.tax is not None and data.tax != pricing.tax:
        # Save old tax value before updating
        history = PricingTaxHistory(
            pricing_id=pricing.id,
            item_id=pricing.item_id,
            old_tax=pricing.tax,
            new_tax=data.tax
        )
        db.add(history)

        pricing.tax = data.tax
        pricing.cgst_rate = data.tax / 2
        pricing.sgst_rate = data.tax / 2

    if data.calories is not None:
        pricing.calories = data.calories

    if data.is_active is not None:
        pricing.is_active = data.is_active

    await db.commit()
    await db.refresh(pricing)

    return pricing


# =========================================================
# DELETE PRICING
# =========================================================

@router.delete("/delete_pricing/{pricing_id}")
async def delete_pricing(
    pricing_id: int,
    db: SessionDep,
    current=Depends(access_four)
):

    result = await db.execute(
        select(Pricing).where(
            Pricing.id == pricing_id
        )
    )

    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(
            404,
            "Pricing not found"
        )

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


@router.get(
    "/item/{item_id}/tax-history",
    response_model=list[TaxHistoryOut]
)
async def get_item_tax_history(
    item_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    
    role = current["role"]
    user = current["user"]

    if role == UserRole.CLIENT:
        client_id = user.id

    elif role == UserRole.STAFF:
        client_id = user.client_id

    else:
        raise HTTPException(
            403,
            "Access denied"
        )

    pricing_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == item_id,
            Pricing.client_id == client_id
        )
    )

    pricing = pricing_result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(
            404,
            "Pricing not found"
        )

    result = await db.execute(
        select(PricingTaxHistory)
        .where(
            PricingTaxHistory.pricing_id == pricing.id
        )
        .order_by(
            PricingTaxHistory.created_at.desc()
        )
    )


    return result.scalars().all()

