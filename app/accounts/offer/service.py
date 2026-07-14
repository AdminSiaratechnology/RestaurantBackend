# app/accounts/offer/service.py

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.accounts.offer.model import Offer
from app.accounts.offer.schema import (
    OfferCreate,
    OfferUpdate
)
from app.accounts.deps import UserRole
from sqlalchemy import select
from datetime import datetime
from app.accounts.branch.model import Branch
from app.accounts.offer.model import Offer
from app.accounts.enum import UserRole

# =========================================
# CREATE OFFER
# =========================================

async def create_offer_service(
    db,
    data: OfferCreate,
    current
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        data.branch_id = user.branch_id

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


# =========================================
# GET ALL OFFERS
# =========================================

async def get_all_offers_service(
    db,
    branch_id,
    current
):
    role = current["role"]
    user = current["user"]

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


# =========================================
# PAGINATED OFFERS
# =========================================

async def get_offers_paginated_service(
    db,
    branch_id,
    status,
    search,
    cursor,
    limit,
    current
):
    role = current["role"]
    user = current["user"]

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

    if status and status not in ["all", "festival"]:
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
                (Offer.valid_to < now) |
                (Offer.is_active == False)
            )

    if search:
        query = query.where(
            Offer.offer_name.ilike(f"%{search}%")
        )

    if cursor is not None:
        query = query.where(
            Offer.id > cursor
        )

    query = query.order_by(
        Offer.id.asc()
    ).limit(limit)

    result = await db.execute(query)

    offers = result.scalars().all()

    return {
        "offers": offers,
        "next_cursor": offers[-1].id if offers else None,
        "has_more": len(offers) == limit
    }


# =========================================
# GET SINGLE OFFER
# =========================================

async def get_offer_service(
    db,
    offer_id,
    current
):
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


# =========================================
# UPDATE OFFER
# =========================================

async def update_offer_service(
    db,
    offer_id,
    data: OfferUpdate,
    current
):
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

    if role == UserRole.STAFF:
        if offer.branch_id != user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Not allowed"
            )

    update_data = data.model_dump(
        exclude_unset=True
    )

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


# =========================================
# DELETE OFFER
# =========================================

async def delete_offer_service(
    db,
    offer_id,
    current
):
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

    if role == UserRole.STAFF:
        if offer.branch_id != user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Not allowed"
            )

    await db.delete(offer)
    await db.commit()

    return {
        "success": True,
        "message": "Offer deleted successfully"
    }





async def get_offers_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "total_offers": 0,
            "active_offers": 0,
            "expired_offers": 0,
            "scheduled_offers": 0,
            "branches": []
        }

    offers_result = await db.execute(
        select(Offer).where(
            Offer.branch_id.in_(branch_ids)
        )
    )

    offers = offers_result.scalars().all()

    now = datetime.utcnow()

    response = {
        "total_offers": len(offers),
        "active_offers": 0,
        "expired_offers": 0,
        "scheduled_offers": 0,
        "branches": []
    }

    # dashboard counters
    for offer in offers:

        if (
            offer.is_active
            and offer.valid_from <= now
            and offer.valid_to >= now
        ):
            response["active_offers"] += 1

        elif (
            offer.is_active
            and offer.valid_from > now
        ):
            response["scheduled_offers"] += 1

        else:
            response["expired_offers"] += 1

    # branch-wise grouping
    for branch in branches:

        branch_offers = [
            o for o in offers
            if o.branch_id == branch.id
        ]

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_offers": len(branch_offers),

            "offers": [
                {
                    "id": o.id,
                    "offer_name": o.offer_name,
                    "description": o.description,
                    "offer_type": o.offer_type.value,
                    "discount_value": o.discount_value,
                    "min_order_amount": o.min_order_amount,
                    "valid_from": o.valid_from,
                    "valid_to": o.valid_to,
                    "is_active": o.is_active,

                    "offer_status":
                    (
                        "active"
                        if (
                            o.is_active
                            and o.valid_from <= now
                            and o.valid_to >= now
                        )
                        else "scheduled"
                        if (
                            o.is_active
                            and o.valid_from > now
                        )
                        else "expired"
                    )
                }
                for o in branch_offers
            ]
        })

    return response



from sqlalchemy import select

from app.accounts.offer.model import Offer


async def get_offer_usage_service(
    db,
    offer_id: int,
    current
):
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

    return {
        "offer_id": offer.id,
        "offer_name": offer.offer_name,
        "total_used": offer.no_used
    }