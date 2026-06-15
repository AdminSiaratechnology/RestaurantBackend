from fastapi import (
    APIRouter,
    HTTPException
)

from sqlalchemy import select

from app.db.config import SessionDep

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.payment.model import Payment

from app.accounts.payment.schema import (
    PaymentCreate,
    PaymentOut
)
from app.accounts.offer.model import Offer, OfferType





router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)


@router.post(
    "/pay",
    response_model=PaymentOut
)
async def make_payment(
    data: PaymentCreate,
    db: SessionDep
):

    # =====================================
    # BILL
    # =====================================

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == data.bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:

        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # =====================================
    # ALREADY PAID
    # =====================================

    if bill.payment_status == PaymentStatus.complete:

        raise HTTPException(
            status_code=400,
            detail="Bill already paid"
        )

    # =====================================
    # DETERMINE FINAL AMOUNT TO PAY
    # =====================================
    # Use final_amount from request if provided, otherwise use due_amount
    amount_to_pay = data.final_amount if (data.final_amount is not None and data.final_amount > 0) else bill.due_amount

    # =====================================
    # VALIDATION
    # =====================================

    total_received = sum(
        item.payment_amount
        for item in data.payments
    )

    if total_received < amount_to_pay:
        raise HTTPException(
            status_code=400,
            detail=f"Amount should be at least {amount_to_pay}"
        )

    # =====================================
    # CHANGE
    # =====================================

    change_amount = round(
        total_received - amount_to_pay,
        2
    )

    payment_breakdown = [
        {
            "payment_method": item.payment_method.value,
            "payment_amount": item.payment_amount
        }
        for item in data.payments
    ]

    # =====================================
    # PAYMENT ENTRY
    # =====================================

    payment = Payment(
        bill_id=bill.id,
        order_id=bill.order_id,
        branch_id=bill.branch_id,
        payment_method=(
            "split"
        if len(data.payments) > 1
        else data.payments[0].payment_method.value
        ),

        payment_breakdown=payment_breakdown,

        bill_amount=bill.grand_total,

        receive_amount=total_received,

        paid_amount=amount_to_pay,

        change_amount=change_amount,

        payment_reference=data.payment_reference,

        notes=data.notes,

        offer_id=data.offer_id,

        offer_discount=data.offer_discount or 0
    )

    db.add(payment)

    # =====================================
    # NOW UPDATE BILL - ONLY AFTER CREATING PAYMENT!
    # =====================================

    # Update bill fields with offer info if provided
    if data.offer_id and data.offer_id > 0:
        bill.offer_id = data.offer_id
        bill.offer_discount = data.offer_discount or 0
    else:
        bill.offer_id = None
        bill.offer_discount = 0

    bill.final_amount = amount_to_pay

    # Update payment status and other fields
    bill.paid_amount = amount_to_pay

    bill.due_amount = 0

    bill.payment_status = (
        PaymentStatus.complete
    )

    bill.payment_method = (
        "split"
        if len(data.payments) > 1
        else data.payments[0].payment_method.value
    )

    await db.commit()

    await db.refresh(payment)

    return payment





@router.patch("/apply-offer/{bill_id}")
async def apply_offer(
    db: SessionDep,
    bill_id: int,
    offer_id: int | None = None
):
    """
    Preview an offer application (NO DATABASE UPDATES).
    If offer_id is None, preview without any offer.
    """

    bill_result = await db.execute(
        select(Bill).where(Bill.id == bill_id)
    )

    bill = bill_result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # If no offer, return original amount
    if not offer_id:
        return {
            "bill_id": bill.id,
            "offer_id": None,
            "offer_discount": 0.0,
            "grand_total": bill.grand_total,
            "final_amount": bill.grand_total
        }

    offer_result = await db.execute(
        select(Offer).where(
            Offer.id == offer_id
        )
    )

    offer = offer_result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=404,
            detail="Offer not found"
        )

    original_amount = bill.grand_total

    discount = 0.0

    if offer.offer_type == OfferType.FLAT_DISCOUNT:

        discount = min(
            offer.discount_value or 0,
            original_amount
        )

    elif offer.offer_type == OfferType.PERCENTAGE_OFF:

        discount = round(
            original_amount *
            ((offer.discount_value or 0) / 100),
            2
        )

    final_amount = max(
        0,
        original_amount - discount
    )

    # NO DATABASE COMMIT - JUST RETURN PREVIEW
    return {
        "bill_id": bill.id,
        "offer_id": offer.id,
        "offer_discount": discount,
        "grand_total": original_amount,
        "final_amount": final_amount
    }