# app/accounts/payment/service.py

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.payment.model import Payment

from app.accounts.offer.model import (
    Offer,
    OfferType
)
from app.core.cache import Cache


# =====================================
# HELPER
# =====================================

async def get_bill_or_404(
    db,
    bill_id: int
):
    result = await db.execute(
        select(Bill).where(
            Bill.id == bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    return bill


async def get_offer_or_404(
    db,
    offer_id: int
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

    return offer


# =====================================
# MAKE PAYMENT
# =====================================

async def make_payment_service(
    db,
    data
):
    # Validate payments exist
    if not data.payments:
        raise HTTPException(
            status_code=400,
            detail="At least one payment method is required"
        )

    bill = await get_bill_or_404(db, data.bill_id)

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Bill already paid"
        )

    # Calculate payable amount
    amount_to_pay = (
        data.final_amount
        if (data.final_amount is not None and data.final_amount > 0)
        else bill.due_amount
    )

    total_received = sum(
        item.payment_amount for item in data.payments
    )

    if total_received < amount_to_pay:
        raise HTTPException(
            status_code=400,
            detail=f"Amount should be at least {amount_to_pay}"
        )

    change_amount = round(
        total_received - amount_to_pay,
        2
    )

    # Payment method
    is_split_payment = len(data.payments) > 1

    payment_method = (
        "split"
        if is_split_payment
        else data.payments[0].payment_method.value
    )

    # Payment breakdown
    payment_breakdown = [
        {
            "payment_method": item.payment_method.value,
            "payment_amount": item.payment_amount
        }
        for item in data.payments
    ]

    # -----------------------------
    # Normalize Offer ID
    # -----------------------------
    offer_id = (
        data.offer_id
        if data.offer_id is not None and data.offer_id > 0
        else None
    )

    # Create Payment
    payment = Payment(
        bill_id=bill.id,
        order_id=bill.order_id,
        branch_id=bill.branch_id,
        payment_method=payment_method,
        payment_breakdown=payment_breakdown,
        bill_amount=bill.grand_total,
        receive_amount=total_received,
        paid_amount=amount_to_pay,
        change_amount=change_amount,
        payment_reference=data.payment_reference,
        notes=data.notes,
        offer_id=offer_id,
        offer_discount=data.offer_discount or 0
    )

    db.add(payment)

    try:
        # -----------------------------
        # Apply Offer
        # -----------------------------
        if offer_id:

            offer = await get_offer_or_404(
                db,
                offer_id
            )

            bill.offer_id = offer.id
            bill.offer_discount = data.offer_discount or 0

            offer.no_used += 1

        else:

            bill.offer_id = None
            bill.offer_discount = 0

        # -----------------------------
        # Update Bill
        # -----------------------------
        bill.final_amount = amount_to_pay
        bill.paid_amount = amount_to_pay
        bill.due_amount = 0
        bill.payment_status = PaymentStatus.complete
        bill.payment_method = payment_method

        await db.commit()

        await db.refresh(payment)

        # Clear cache
        await Cache.delete_pattern(
            f"dashboard:*:branch:{bill.branch_id}"
        )

        await Cache.delete(
            f"invoice:pdf:{bill.id}"
        )

        return payment

    except Exception as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Payment processing failed: {str(e)}"
        )

# =====================================
# APPLY OFFER (PREVIEW ONLY)
# =====================================

async def apply_offer_service(
    db,
    bill_id: int,
    offer_id: int | None
):
    bill = await get_bill_or_404(
        db,
        bill_id
    )

    if not offer_id:

        return {
            "bill_id": bill.id,
            "offer_id": None,
            "offer_discount": 0.0,
            "grand_total": bill.grand_total,
            "final_amount": bill.grand_total
        }

    offer = await get_offer_or_404(
        db,
        offer_id
    )

    original_amount = bill.grand_total

    discount = 0.0

    if offer.offer_type == OfferType.FLAT_DISCOUNT:

        discount = min(
            offer.discount_value or 0,
            original_amount
        )

    elif (
        offer.offer_type ==
        OfferType.PERCENTAGE_OFF
    ):

        discount = round(
            original_amount *
            (
                (offer.discount_value or 0)
                / 100
            ),
            2
        )

    final_amount = max(
        0,
        original_amount - discount
    )

    return {
        "bill_id": bill.id,
        "offer_id": offer.id,
        "offer_discount": discount,
        "grand_total": original_amount,
        "final_amount": final_amount
    }