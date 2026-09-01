# =========================================================
# app/accounts/pricing/service.py
# =========================================================

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.item.model import Item
from app.accounts.pricing.model import (
    Pricing,
    PricingTaxHistory,
)
from app.accounts.deps import (
    UserRole,
    get_client_if_accessible,
)
from app.accounts.branch.model import Branch
from app.core.tax import get_branch_tax_config
from app.core.cache import Cache


# =========================================================
# HELPER
# GET BRANCH TAX CONFIGURATION
# =========================================================

async def get_pricing_tax_config(
    db,
    branch_id: int,
    tax_rate: float,
) -> dict:

    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:

        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    return get_branch_tax_config(
        tax_type=branch.tax_type,
        tax_rate=tax_rate,
    )


# =========================================================
# CREATE PRICING
# =========================================================

async def create_pricing_service(
    db,
    data,
    client,
):

    # =====================================================
    # GET ITEM
    # =====================================================

    result = await db.execute(
        select(Item).where(
            Item.id == data.item_id,
            Item.client_id == client.id,
        )
    )

    item = result.scalar_one_or_none()

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    # =====================================================
    # VALIDATE ITEM BRANCH
    # =====================================================

    if item.branch_id != data.branch_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "branch_id must match the item's branch"
            ),
        )

    # =====================================================
    # GET BRANCH
    # =====================================================

    branch_result = await db.execute(
        select(Branch).where(
            Branch.id == data.branch_id,
            Branch.client_id == client.id,
        )
    )

    branch = branch_result.scalar_one_or_none()

    if not branch:

        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    # =====================================================
    # GET TAX CONFIG
    #
    # INDIA -> GST
    # OTHER -> VAT
    # =====================================================

    tax_config = get_branch_tax_config(
        tax_type=branch.tax_type,
        tax_rate=data.tax,
    )

    # =====================================================
    # CHECK EXISTING PRICING
    # =====================================================

    result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == data.item_id,
            Pricing.client_id == client.id,
            Pricing.branch_id == data.branch_id,
        )
    )

    pricing = result.scalar_one_or_none()

    # =====================================================
    # UPDATE EXISTING
    # =====================================================

    if pricing:

        pricing.price = data.price
        pricing.cost_price = data.cost_price
        pricing.discount = data.discount

        pricing.tax = data.tax
        pricing.tax_type = tax_config["tax_type"]
        pricing.cgst_rate = tax_config["cgst_rate"]
        pricing.sgst_rate = tax_config["sgst_rate"]

        pricing.calories = data.calories
        pricing.is_active = data.is_active

    # =====================================================
    # CREATE NEW
    # =====================================================

    else:

        pricing = Pricing(

            client_id=client.id,

            branch_id=data.branch_id,

            item_id=data.item_id,

            price=data.price,

            cost_price=data.cost_price,

            discount=data.discount,

            # TAX
            tax=data.tax,

            tax_type=tax_config["tax_type"],

            cgst_rate=tax_config["cgst_rate"],

            sgst_rate=tax_config["sgst_rate"],

            # EXTRA
            calories=data.calories,

            is_active=data.is_active,
        )

        db.add(pricing)

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()

    await db.refresh(pricing)

    # =====================================================
    # CLEAR CACHE
    # =====================================================

    await Cache.clear_menu_cache(
        data.branch_id,
        client.id,
    )

    return pricing


# =========================================================
# GET PRICINGS
# =========================================================

async def get_pricings_service(
    db,
    current,
    branch_id=None,
    item_id=None,
):

    role = current["role"]
    user = current["user"]

    # =====================================================
    # CLIENT
    # =====================================================

    if role == UserRole.CLIENT:

        client_id = user.id

    # =====================================================
    # STAFF
    # =====================================================

    elif role == UserRole.STAFF:

        client_id = user.client_id

        if branch_id is None:

            branch_id = user.branch_id

    # =====================================================
    # INVALID
    # =====================================================

    else:

        raise HTTPException(
            status_code=400,
            detail="Client context not found",
        )

    # =====================================================
    # QUERY
    # =====================================================

    query = select(Pricing).where(
        Pricing.client_id == client_id
    )

    if branch_id:

        query = query.where(
            Pricing.branch_id == branch_id
        )

    if item_id:

        query = query.where(
            Pricing.item_id == item_id
        )

    result = await db.execute(query)

    return result.scalars().all()


# =========================================================
# UPDATE PRICING
# =========================================================

async def update_pricing_service(
    db,
    pricing_id,
    data,
    current,
):

    # =====================================================
    # GET PRICING
    # =====================================================

    result = await db.execute(
        select(Pricing).where(
            Pricing.id == pricing_id
        )
    )

    pricing = result.scalar_one_or_none()

    if not pricing:

        raise HTTPException(
            status_code=404,
            detail="Pricing not found",
        )

    # =====================================================
    # ACCESS CHECK
    # =====================================================

    await get_client_if_accessible(
        client_id=pricing.client_id,
        db=db,
        current=current,
    )

    # =====================================================
    # GET BRANCH
    # =====================================================

    branch_result = await db.execute(
        select(Branch).where(
            Branch.id == pricing.branch_id
        )
    )

    branch = branch_result.scalar_one_or_none()

    if not branch:

        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    # =====================================================
    # UPDATE PRICE
    # =====================================================

    if data.price is not None:

        pricing.price = data.price

    if data.cost_price is not None:

        pricing.cost_price = data.cost_price

    if data.discount is not None:

        pricing.discount = data.discount

    # =====================================================
    # UPDATE TAX
    # =====================================================

    if data.tax is not None:

        # -----------------------------------------------
        # CREATE TAX HISTORY
        # -----------------------------------------------

        if data.tax != pricing.tax:

            history = PricingTaxHistory(

                pricing_id=pricing.id,

                item_id=pricing.item_id,

                old_tax=pricing.tax,

                new_tax=data.tax,
            )

            db.add(history)

        # -----------------------------------------------
        # GET COUNTRY BASED TAX CONFIG
        # -----------------------------------------------

        tax_config = get_branch_tax_config(

            tax_type=branch.tax_type,

            tax_rate=data.tax,
        )

        # -----------------------------------------------
        # UPDATE TAX
        # -----------------------------------------------

        pricing.tax = data.tax

        pricing.tax_type = (
            tax_config["tax_type"]
        )

        pricing.cgst_rate = (
            tax_config["cgst_rate"]
        )

        pricing.sgst_rate = (
            tax_config["sgst_rate"]
        )

    # =====================================================
    # UPDATE OTHER FIELDS
    # =====================================================

    if data.calories is not None:

        pricing.calories = data.calories

    if data.is_active is not None:

        pricing.is_active = data.is_active

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()

    await db.refresh(pricing)

    # =====================================================
    # CLEAR CACHE
    # =====================================================

    await Cache.clear_menu_cache(

        pricing.branch_id,

        pricing.client_id,
    )

    return pricing


# =========================================================
# DELETE PRICING
# =========================================================

async def delete_pricing_service(
    db,
    pricing_id,
    current,
):

    result = await db.execute(
        select(Pricing).where(
            Pricing.id == pricing_id
        )
    )

    pricing = result.scalar_one_or_none()

    if not pricing:

        raise HTTPException(
            status_code=404,
            detail="Pricing not found",
        )

    await get_client_if_accessible(
        client_id=pricing.client_id,
        db=db,
        current=current,
    )

    branch_id = pricing.branch_id

    client_id = pricing.client_id

    await db.delete(pricing)

    await db.commit()

    await Cache.clear_menu_cache(
        branch_id,
        client_id,
    )

    return {
        "message": "Pricing deleted successfully",
    }


# =========================================================
# TAX HISTORY
# =========================================================

async def get_item_tax_history_service(
    db,
    item_id,
    current,
):

    role = current["role"]

    user = current["user"]

    if role == UserRole.CLIENT:

        client_id = user.id

    elif role == UserRole.STAFF:

        client_id = user.client_id

    else:

        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    pricing_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == item_id,
            Pricing.client_id == client_id,
        )
    )

    pricing = pricing_result.scalar_one_or_none()

    if not pricing:

        raise HTTPException(
            status_code=404,
            detail="Pricing not found",
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