# =========================================================
# app/accounts/pricing/routers.py
# =========================================================

from fastapi import APIRouter, Depends

from app.db.config import SessionDep

from app.accounts.pricing.schema import (
    PricingCreate,
    PricingUpdate,
    PricingOut,
    TaxHistoryOut
)

from app.accounts.deps import (
    access_four,
    require_client
)

from app.accounts.pricing.service import (
    create_pricing_service,
    get_pricings_service,
    update_pricing_service,
    delete_pricing_service,
    get_item_tax_history_service
)

router = APIRouter(
    prefix="/pricing",
    tags=["Pricing"]
)


@router.post(
    "/set_pricing",
    response_model=PricingOut
)
async def create_pricing(
    data: PricingCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    return await create_pricing_service(
        db=db,
        data=data,
        client=current["user"]
    )


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
    return await get_pricings_service(
        db=db,
        current=current,
        branch_id=branch_id,
        item_id=item_id
    )


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
    return await update_pricing_service(
        db=db,
        pricing_id=pricing_id,
        data=data,
        current=current
    )


@router.delete(
    "/delete_pricing/{pricing_id}"
)
async def delete_pricing(
    pricing_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    return await delete_pricing_service(
        db=db,
        pricing_id=pricing_id,
        current=current
    )


@router.get(
    "/item/{item_id}/tax-history",
    response_model=list[TaxHistoryOut]
)
async def get_item_tax_history(
    item_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_item_tax_history_service(
        db=db,
        item_id=item_id,
        current=current
    )