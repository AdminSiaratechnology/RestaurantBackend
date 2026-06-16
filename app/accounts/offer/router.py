# app/accounts/offer/router.py

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.accounts.offer.schema import (
    OfferCreate,
    OfferUpdate,
    OfferResponse
)

from app.accounts.offer.model import Offer
from app.db.config import SessionDep

from app.accounts.deps import (
    access_four,
    UserRole
)

router = APIRouter(
    prefix="/offers",
    tags=["Offers"]
)


# =========================================
# CREATE OFFER
# =========================================

@router.post("/create", response_model=OfferResponse)
async def create_offer(
    data: OfferCreate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        role = current["role"]
        user = current["user"]

        # STAFF restriction
        if role == UserRole.STAFF:
            data.branch_id = user.branch_id

        # FIX TIMEZONE ISSUE
        valid_from = data.valid_from.replace(tzinfo=None)
        valid_to = data.valid_to.replace(tzinfo=None)

        offer = Offer(
            branch_id=data.branch_id,

            offer_name=data.offer_name,
            description=data.description,

            offer_type=data.offer_type.value,

            discount_value=data.discount_value,
            min_order_amount=data.min_order_amount,

            valid_from=valid_from,
            valid_to=valid_to,

            is_active=True
        )

        db.add(offer)

        await db.commit()
        await db.refresh(offer)

        return offer

    except HTTPException as e:
        await db.rollback()
        raise e

    except Exception as e:
        await db.rollback()

        print("CREATE OFFER ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================
# GET ALL OFFERS
# =========================================

@router.get("/all")
async def get_all_offers(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:

        role = current["role"]
        user = current["user"]

        # STAFF restriction
        if role == UserRole.STAFF:
            branch_id = user.branch_id

        if not branch_id:
            raise HTTPException(
                status_code=400,
                detail="branch_id is required"
            )

        result = await db.execute(
            select(Offer).where(
                Offer.branch_id == branch_id
            )
        )

        offers = result.scalars().all()

        return {
            "success": True,
            "count": len(offers),
            "data": offers
        }

    except HTTPException as e:
        raise e

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


# =========================================
# GET PAGINATED OFFERS
# =========================================

@router.get("/paginated")
async def get_offers_paginated(
    db: SessionDep,
    branch_id: int | None = None,
    status: str | None = None,   # "active" | "scheduled" | "expired" | "all"
    search: str | None = None,
    cursor: int | None = None,
    limit: int = 50,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        # STAFF restriction
        if role == UserRole.STAFF:
            branch_id = user.branch_id

        if not branch_id:
            raise HTTPException(
                status_code=400,
                detail="branch_id is required"
            )

        query = select(Offer).where(
            Offer.branch_id == branch_id
        )

        if status and status != "all" and status != "festival":
            now = datetime.utcnow()
            if status == "active":
                query = query.where(
                    Offer.is_active == True,
                    Offer.valid_from <= now,
                    Offer.valid_to >= now
                )
            elif status == "scheduled":
                query = query.where(
                    Offer.is_active == True,
                    Offer.valid_from > now
                )
            elif status == "expired":
                query = query.where(
                    (Offer.valid_to < now) | (Offer.is_active == False)
                )

        if search:
            query = query.where(
                Offer.offer_name.ilike(f"%{search}%")
            )

        if cursor is not None:
            query = query.where(Offer.id > cursor)

        query = query.order_by(Offer.id.asc()).limit(limit)

        result = await db.execute(query)
        offers = result.scalars().all()

        next_cursor = offers[-1].id if offers else None
        has_more = len(offers) == limit

        return {
            "offers": offers,
            "next_cursor": next_cursor,
            "has_more": has_more
        }

    except HTTPException as e:
        raise e

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


# =========================================
# GET SINGLE OFFER
# =========================================

@router.get("/{offer_id}")
async def get_offer(
    offer_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        result = await db.execute(
            select(Offer).where(
                Offer.id == offer_id
            )
        )

        offer = result.scalar_one_or_none()

        if not offer:
            raise HTTPException(
                status_code=404,
                detail="Offer not found"
            )

        role = current["role"]
        user = current["user"]

        # STAFF restriction
        if role == UserRole.STAFF:
            if offer.branch_id != user.branch_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not allowed"
                )

        return {
            "success": True,
            "data": offer
        }

    except HTTPException as e:
        raise e

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


# =========================================
# UPDATE OFFER
# =========================================


from datetime import timezone

@router.put("/update/{offer_id}")
async def update_offer(
    offer_id: int,
    data: OfferUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        result = await db.execute(
            select(Offer).where(
                Offer.id == offer_id
            )
        )

        offer = result.scalar_one_or_none()

        if not offer:
            raise HTTPException(
                status_code=404,
                detail="Offer not found"
            )

        role = current["role"]
        user = current["user"]

        # STAFF restriction
        if role == UserRole.STAFF:
            if offer.branch_id != user.branch_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not allowed to update another branch offer"
                )

        update_data = data.dict(exclude_unset=True)

        # FIX TIMEZONE ISSUE
        for field in ["valid_from", "valid_to"]:
            if field in update_data and update_data[field]:
                update_data[field] = (
                    update_data[field]
                    .astimezone(timezone.utc)
                    .replace(tzinfo=None)
                )

        for key, value in update_data.items():
            setattr(offer, key, value)

        await db.commit()
        await db.refresh(offer)

        return {
            "success": True,
            "message": "Offer updated successfully",
            "data": offer
        }

    except HTTPException as e:
        await db.rollback()
        raise e

    except SQLAlchemyError as e:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

# =========================================
# DELETE OFFER
# =========================================


@router.delete("/delete/{offer_id}")
async def delete_offer(
    offer_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        result = await db.execute(
            select(Offer).where(
                Offer.id == offer_id
            )
        )

        offer = result.scalar_one_or_none()

        if not offer:
            raise HTTPException(
                status_code=404,
                detail="Offer not found"
            )

        role = current["role"]
        user = current["user"]

        # STAFF restriction
        if role == UserRole.STAFF:
            if offer.branch_id != user.branch_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not allowed to delete another branch offer"
                )

        # DELETE OFFER
        await db.delete(offer)

        # SAVE CHANGES
        await db.commit()

        return {
            "success": True,
            "message": "Offer deleted successfully"
        }

    except HTTPException as e:
        await db.rollback()
        raise e

    except SQLAlchemyError as e:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    except Exception as e:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )