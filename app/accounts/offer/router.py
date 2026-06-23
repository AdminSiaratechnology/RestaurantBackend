# app/accounts/offer/router.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.db.config import SessionDep

from app.accounts.offer.schema import (
    OfferCreate,
    OfferUpdate,
    OfferResponse
)

from app.accounts.offer.service import (
    create_offer_service,
    get_all_offers_service,
    get_offer_usage_service,
    get_offers_paginated_service,
    get_offer_service,
    update_offer_service,
    delete_offer_service,
    get_offers_all_branches_service
)

from app.accounts.deps import access_four

router = APIRouter(
    prefix="/offers",
    tags=["Offers"]
)


@router.post("/create", response_model=OfferResponse)
async def create_offer(
    data: OfferCreate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        return await create_offer_service(
            db,
            data,
            current
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/all")
async def get_all_offers(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    return await get_all_offers_service(
        db,
        branch_id,
        current
    )


@router.get("/paginated")
async def get_offers_paginated(
    db: SessionDep,
    branch_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    cursor: int | None = None,
    limit: int = 50,
    current=Depends(access_four)
):
    return await get_offers_paginated_service(
        db,
        branch_id,
        status,
        search,
        cursor,
        limit,
        current
    )


@router.get("/{offer_id}")
async def get_offer(
    offer_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_offer_service(
        db,
        offer_id,
        current
    )


@router.put("/update/{offer_id}")
async def update_offer(
    offer_id: int,
    data: OfferUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        return await update_offer_service(
            db,
            offer_id,
            data,
            current
        )
    except Exception:
        await db.rollback()
        raise


@router.delete("/delete/{offer_id}")
async def delete_offer(
    offer_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        return await delete_offer_service(
            db,
            offer_id,
            current
        )
    except Exception:
        await db.rollback()
        raise

@router.get("/dashboard/all-branches")
async def offers_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_offers_all_branches_service(
        db,
        current
    )



@router.get("/{offer_id}/usage")
async def get_offer_usage(
    offer_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_offer_usage_service(
        db,
        offer_id,
        current
    )