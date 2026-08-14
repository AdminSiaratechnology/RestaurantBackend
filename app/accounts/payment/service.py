from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.payment.model import Payment
from app.accounts.payment.schema import PaymentCreate

from app.accounts.offer.model import Offer
from app.accounts.offer.helper import (
    validate_and_calculate_offer,
    calculate_final_amount,
)

from app.accounts.crm.wallet.service import (
    calculate_wallet_discount,
    debit_wallet,
)

from app.core.cache import Cache


# =========================================================
# BILL
# =========================================================

async def get_bill_or_404(
    db,
    bill_id: int,
) -> Bill:

    result = await db.execute(
        select(Bill)
        .where(Bill.id == bill_id)
        .with_for_update()
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    return bill


# =========================================================
# OFFER
# =========================================================

async def get_offer_or_404(
    db,
    offer_id: int,
) -> Offer:

    result = await db.execute(
        select(Offer)
        .where(Offer.id == offer_id)
    )

    offer = result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=404,
            detail="Offer not found",
        )

    return offer


# =========================================================
# OFFER PREVIEW
# =========================================================

async def apply_offer_service(
    db,
    bill_id: int,
    offer_id: int | None = None,
):

    bill = await get_bill_or_404(
        db,
        bill_id,
    )

    if not offer_id:

        return {
            "bill_id": bill.id,
            "offer_id": None,
            "original_amount": bill.grand_total,
            "offer_discount": 0.0,
            "final_amount": bill.grand_total,
            "due_amount": bill.grand_total,
            "message": "No offer applied",
        }

    offer = await get_offer_or_404(
        db,
        offer_id,
    )

    discount = validate_and_calculate_offer(
        offer,
        bill.grand_total,
    )

    final_amount = calculate_final_amount(
        bill.grand_total,
        discount,
    )

    return {
        "bill_id": bill.id,
        "offer_id": offer.id,
        "original_amount": bill.grand_total,
        "offer_discount": discount,
        "final_amount": final_amount,
        "due_amount": final_amount,
        "message": "Offer applied successfully",
    }


# =========================================================
# MAKE PAYMENT
# =========================================================

async def make_payment_service(
    db,
    data: PaymentCreate,
):

    # =====================================================
    # VALIDATE PAYMENTS
    # =====================================================

    if not data.payments:
        raise HTTPException(
            status_code=400,
            detail="At least one payment method is required",
        )

    # =====================================================
    # GET BILL + LOCK
    # =====================================================

    bill = await get_bill_or_404(
        db,
        data.bill_id,
    )

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Bill is already paid",
        )

    # =====================================================
    # OFFER
    # =====================================================

    offer = None

    offer_id = data.offer_id

    offer_discount = 0.0

    if offer_id:

        offer = await get_offer_or_404(
            db,
            offer_id,
        )

        offer_discount = validate_and_calculate_offer(
            offer,
            bill.grand_total,
        )

    # =====================================================
    # AMOUNT AFTER OFFER
    # =====================================================

    amount_after_offer = calculate_final_amount(
        bill.grand_total,
        offer_discount,
    )

    # =====================================================
    # CRM WALLET SPECIAL DISCOUNT
    # =====================================================

    wallet_discount = 0.0

    wallet_info = {
        "wallet_balance": 0.0,
        "wallet_percent": 0.0,
        "max_wallet_discount": 0.0,
        "wallet_discount": 0.0,
    }

    if data.use_wallet:

        # -------------------------------------------------
        # CUSTOMER REQUIRED
        # -------------------------------------------------

        if not bill.customer_id:

            raise HTTPException(
                status_code=400,
                detail=(
                    "CRM customer is required "
                    "to use wallet discount"
                ),
            )

        # -------------------------------------------------
        # CALCULATE WALLET DISCOUNT
        # -------------------------------------------------

        wallet_info = await calculate_wallet_discount(
            db=db,
            customer_id=bill.customer_id,
            client_id=bill.client_id,
            branch_id=bill.branch_id,
            amount=amount_after_offer,
        )

        wallet_discount = wallet_info[
            "wallet_discount"
        ]

    # =====================================================
    # FINAL PAYABLE
    # =====================================================

    final_amount = round(
        amount_after_offer - wallet_discount,
        2,
    )

    if final_amount < 0:
        final_amount = 0.0

    # =====================================================
    # RECEIVED AMOUNT
    # =====================================================

    total_received = round(
        sum(
            p.payment_amount
            for p in data.payments
        ),
        2,
    )

    # =====================================================
    # VALIDATE PAYMENT
    # =====================================================

    if total_received < final_amount:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient amount received. "
                f"Amount due: {final_amount}"
            ),
        )

    # =====================================================
    # CHANGE
    # =====================================================

    change_amount = round(
        total_received - final_amount,
        2,
    )

    # =====================================================
    # PAYMENT METHOD
    # =====================================================

    payment_method = (
        "split"
        if len(data.payments) > 1
        else data.payments[0].payment_method.value
    )

    # =====================================================
    # PAYMENT BREAKDOWN
    # =====================================================

    payment_breakdown = [
        {
            "payment_method": p.payment_method.value,
            "payment_amount": round(
                p.payment_amount,
                2,
            ),
        }
        for p in data.payments
    ]

    # =====================================================
    # CREATE PAYMENT
    # =====================================================

    payment = Payment(
        bill_id=bill.id,
        order_id=bill.order_id,
        branch_id=bill.branch_id,

        payment_method=payment_method,

        payment_breakdown=payment_breakdown,

        bill_amount=bill.grand_total,

        receive_amount=total_received,

        paid_amount=final_amount,

        change_amount=change_amount,

        payment_reference=data.payment_reference,

        notes=data.notes,

        offer_id=offer_id,

        offer_discount=offer_discount,

        wallet_discount=wallet_discount,
    )

    db.add(payment)

    try:

        # =================================================
        # WALLET DEBIT
        # =================================================

        if wallet_discount > 0:

            await debit_wallet(
                db=db,
                customer_id=bill.customer_id,
                client_id=bill.client_id,
                branch_id=bill.branch_id,
                amount=wallet_discount,
                reference_type="BILL",
                reference_id=bill.id,
                notes="CRM wallet special discount",
            )

        # =================================================
        # OFFER USAGE
        # =================================================

        if offer:

            offer.no_used += 1

        # =================================================
        # UPDATE BILL
        # =================================================

        bill.paid_amount = final_amount

        bill.due_amount = 0.0

        bill.payment_status = PaymentStatus.complete

        bill.payment_method = payment_method

        bill.offer_id = offer_id

        bill.offer_discount = offer_discount

        bill.wallet_discount = wallet_discount

        bill.final_amount = final_amount

        # =================================================
        # COMMIT
        # =================================================

        await db.commit()

        await db.refresh(payment)

        # =================================================
        # CACHE
        # =================================================

        await Cache.delete_pattern(
            f"dashboard:*:branch:{bill.branch_id}"
        )

        await Cache.delete(
            f"invoice:pdf:{bill.id}"
        )

        return payment

    except SQLAlchemyError as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Payment processing failed: {str(e)}"
            ),
        )