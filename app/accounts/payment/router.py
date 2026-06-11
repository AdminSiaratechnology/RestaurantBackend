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

    if data.receive_amount < amount_to_pay:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Amount should be at least "
                f"{amount_to_pay}"
            )
        )

    # =====================================
    # CHANGE
    # =====================================

    change_amount = round(
        data.receive_amount -
        amount_to_pay,
        2
    )

    # =====================================
    # PAYMENT ENTRY
    # =====================================

    payment = Payment(

        bill_id=bill.id,

        order_id=bill.order_id,

        branch_id=bill.branch_id,

        payment_method=data.payment_method,

        bill_amount=bill.grand_total,  # Always store original bill amount

        receive_amount=data.receive_amount,

        paid_amount=amount_to_pay,  # This is what the customer actually paid

        change_amount=change_amount,

        payment_reference=(
            data.payment_reference
        ),

        notes=data.notes,
        
        # Store offer information on payment
        offer_id=data.offer_id,
        offer_discount=data.offer_discount or 0
    )

    db.add(payment)

    # =====================================
    # NOW UPDATE BILL - ONLY AFTER CREATING PAYMENT!
    # =====================================

    # Update bill fields with offer info if provided
    if data.offer_id is not None:
        bill.offer_id = data.offer_id
        bill.offer_discount = data.offer_discount or 0
        bill.final_amount = amount_to_pay

    # If no offer, set final_amount to grand_total
    else:
        bill.final_amount = amount_to_pay

    # Update payment status and other fields
    bill.paid_amount = amount_to_pay

    bill.due_amount = 0

    bill.payment_status = (
        PaymentStatus.complete
    )

    bill.payment_method = (
        data.payment_method
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