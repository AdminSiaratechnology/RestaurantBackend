# app/accounts/offer/helper.py

from datetime import datetime
from fastapi import HTTPException

from app.accounts.offer.model import Offer, OfferType


def validate_and_calculate_offer(
    offer: Offer,
    grand_total: float
) -> float:
    """
    Single source of truth for offer eligibility + discount math.
    Used by BOTH the read-only preview endpoint and the payment endpoint,
    so the numbers a user previews are guaranteed to match what gets charged.

    Raises HTTPException if the offer isn't currently usable.
    Returns the discount amount (never negative, never more than grand_total).
    """

    if not offer.is_active:
        raise HTTPException(
            status_code=400,
            detail="Offer is not active"
        )

    now = datetime.utcnow()

    if not (offer.valid_from <= now <= offer.valid_to):
        raise HTTPException(
            status_code=400,
            detail="Offer has expired or is not yet valid"
        )

    if grand_total < (offer.min_order_amount or 0):
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order amount is {offer.min_order_amount}"
        )

    discount = 0.0

    if offer.offer_type == OfferType.FLAT_DISCOUNT:
        discount = min(
            float(offer.discount_value or 0),
            grand_total
        )

    elif offer.offer_type == OfferType.PERCENTAGE_OFF:
        discount = round(
            grand_total * (float(offer.discount_value or 0) / 100),
            2
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "This offer type does not support automatic "
                "discount calculation"
            )
        )

    return round(discount, 2)


def calculate_final_amount(
    grand_total: float,
    discount: float
) -> float:
    """Clamp final payable amount to zero, never negative."""
    return max(0.0, round(grand_total - discount, 2))