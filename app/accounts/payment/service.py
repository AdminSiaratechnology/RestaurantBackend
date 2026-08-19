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

from app.accounts.order.model import Order

from app.core.cache import Cache


# ============================================================
# GET BILL + LOCK
# ============================================================


async def get_bill_or_404(
    db,
    bill_id: int,
) -> Bill:

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == bill_id
        )
        .with_for_update()
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    return bill


# ============================================================
# RESOLVE CRM CUSTOMER
# ============================================================


async def resolve_bill_customer(
    db,
    bill: Bill,
):
    """
    Resolve customer from Bill first.

    If Bill.customer_id is missing,
    fallback to Order.customer_id.

    The bill is synchronized with the resolved customer.
    """

    if bill.customer_id:
        return bill.customer_id

    if not bill.order_id:
        return None

    result = await db.execute(
        select(Order.customer_id)
        .where(
            Order.id == bill.order_id
        )
    )

    customer_id = result.scalar_one_or_none()

    if customer_id:
        bill.customer_id = customer_id

    return customer_id


# ============================================================
# GET OFFER
# ============================================================


async def get_offer_or_404(
    db,
    offer_id: int,
) -> Offer:

    result = await db.execute(
        select(Offer)
        .where(
            Offer.id == offer_id
        )
    )

    offer = result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=404,
            detail="Offer not found",
        )

    return offer


# ============================================================
# APPLY OFFER
# ============================================================


async def apply_offer_service(
    db,
    bill_id: int,
    offer_id: int | None = None,
):

    bill = await get_bill_or_404(
        db,
        bill_id,
    )

    original_amount = round(
        float(bill.grand_total or 0),
        2,
    )

    # ========================================================
    # NO OFFER
    # ========================================================

    if not offer_id:

        return {
            "bill_id": bill.id,

            "offer_id": None,

            "original_amount": original_amount,

            "offer_discount": 0.0,

            "final_amount": original_amount,

            "due_amount": original_amount,

            "message": "No offer applied",
        }

    # ========================================================
    # GET OFFER
    # ========================================================

    offer = await get_offer_or_404(
        db,
        offer_id,
    )

    # ========================================================
    # CALCULATE OFFER
    # ========================================================

    discount = validate_and_calculate_offer(
        offer,
        original_amount,
    )

    discount = round(
        float(discount or 0),
        2,
    )

    final_amount = round(
        calculate_final_amount(
            original_amount,
            discount,
        ),
        2,
    )

    if final_amount < 0:
        final_amount = 0.0

    return {
        "bill_id": bill.id,

        "offer_id": offer.id,

        "original_amount": original_amount,

        "offer_discount": discount,

        "final_amount": final_amount,

        "due_amount": final_amount,

        "message": "Offer applied successfully",
    }


# ============================================================
# MAKE PAYMENT
# ============================================================


async def make_payment_service(
    db,
    data: PaymentCreate,
):

    # ========================================================
    # VALIDATE PAYMENT METHODS
    # ========================================================

    if not data.payments:

        raise HTTPException(
            status_code=400,
            detail=(
                "At least one payment method "
                "is required"
            ),
        )

    # ========================================================
    # VALIDATE PAYMENT AMOUNTS
    # ========================================================

    for item in data.payments:

        if item.payment_amount <= 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Payment amount must be "
                    "greater than zero"
                ),
            )

    # ========================================================
    # GET BILL + LOCK
    # ========================================================

    bill = await get_bill_or_404(
        db,
        data.bill_id,
    )

    # ========================================================
    # RESOLVE CUSTOMER
    # ========================================================

    customer_id = await resolve_bill_customer(
        db,
        bill,
    )

    # ========================================================
    # ALREADY PAID
    # ========================================================

    if bill.payment_status == PaymentStatus.complete:

        raise HTTPException(
            status_code=400,
            detail="Bill is already paid",
        )

    # ========================================================
    # ORIGINAL BILL AMOUNT
    # ========================================================

    original_amount = round(
        float(bill.grand_total or 0),
        2,
    )

    if original_amount < 0:
        original_amount = 0.0

    # ========================================================
    # OFFER
    # ========================================================

    offer = None

    offer_discount = 0.0

    if data.offer_id:

        offer = await get_offer_or_404(
            db,
            data.offer_id,
        )

        offer_discount = (
            validate_and_calculate_offer(
                offer,
                original_amount,
            )
        )

        offer_discount = round(
            float(offer_discount or 0),
            2,
        )

    # ========================================================
    # AMOUNT AFTER OFFER
    # ========================================================

    amount_after_offer = round(
        calculate_final_amount(
            original_amount,
            offer_discount,
        ),
        2,
    )

    if amount_after_offer < 0:
        amount_after_offer = 0.0

    # ========================================================
    # WALLET
    # ========================================================
    #
    # VERY IMPORTANT:
    #
    # Wallet is NEVER automatically applied.
    #
    # use_wallet=False:
    #
    #     wallet_discount = 0
    #     final_amount = amount_after_offer
    #
    # use_wallet=True:
    #
    #     calculate wallet contribution
    #     final_amount = amount_after_offer - wallet
    #
    # ========================================================

    wallet_discount = 0.0

    wallet_info = {
        "wallet_available": False,
        "wallet_balance": 0.0,
        "wallet_percent": 0.0,
        "max_wallet_discount": 0.0,
        "wallet_discount": 0.0,
    }

    # ========================================================
    # ONLY CALCULATE WALLET WHEN USER SELECTED IT
    # ========================================================

    if data.use_wallet is True:

        # ----------------------------------------------------
        # CUSTOMER REQUIRED
        # ----------------------------------------------------

        if not customer_id:

            raise HTTPException(
                status_code=400,
                detail=(
                    "CRM customer is required "
                    "to use wallet."
                ),
            )

        # ----------------------------------------------------
        # CALCULATE WALLET CONTRIBUTION
        # ----------------------------------------------------

        wallet_info = (
            await calculate_wallet_discount(
                db=db,
                customer_id=customer_id,
                client_id=bill.client_id,
                branch_id=bill.branch_id,
                amount=amount_after_offer,
                lock_wallet=True,
            )
        )

        wallet_discount = round(
            float(
                wallet_info.get(
                    "wallet_discount",
                    0.0,
                )
            ),
            2,
        )

        if wallet_discount < 0:
            wallet_discount = 0.0

        # Never allow wallet contribution
        # to exceed payable amount.

        if wallet_discount > amount_after_offer:
            wallet_discount = amount_after_offer

    # ========================================================
    # FINAL PAYABLE
    # ========================================================
    #
    # If wallet is NOT selected:
    #
    #     final_amount = amount_after_offer
    #
    # If wallet IS selected:
    #
    #     final_amount = amount_after_offer - wallet_discount
    #
    # ========================================================

    final_amount = round(
        amount_after_offer - wallet_discount,
        2,
    )

    if final_amount < 0:
        final_amount = 0.0

    # ========================================================
    # ACTUAL PAYMENT RECEIVED
    # ========================================================

    total_received = round(
        sum(
            float(item.payment_amount)
            for item in data.payments
        ),
        2,
    )

    # ========================================================
    # VALIDATE ACTUAL PAYMENT
    # ========================================================

    if total_received < final_amount:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient payment amount. "
                f"Final payable after offer"
                f"{' and wallet' if data.use_wallet else ''} "
                f"is ₹{final_amount:.2f}. "
                f"Received ₹{total_received:.2f}."
            ),
        )

    # ========================================================
    # CHANGE
    # ========================================================

    change_amount = round(
        total_received - final_amount,
        2,
    )

    if change_amount < 0:
        change_amount = 0.0

    # ========================================================
    # PAYMENT METHOD
    # ========================================================

    if len(data.payments) > 1:

        payment_method = "split"

    else:

        payment_method = (
            data.payments[0]
            .payment_method
            .value
        )

    # ========================================================
    # PAYMENT BREAKDOWN
    # ========================================================

    payment_breakdown = [
        {
            "payment_method": (
                item.payment_method.value
            ),
            "payment_amount": round(
                float(item.payment_amount),
                2,
            ),
        }
        for item in data.payments
    ]

    # ========================================================
    # CREATE PAYMENT
    # ========================================================

    payment = Payment(

        bill_id=bill.id,

        order_id=bill.order_id,

        branch_id=bill.branch_id,

        # Wallet is NEVER a payment method.
        payment_method=payment_method,

        payment_breakdown=payment_breakdown,

        # Original bill amount.
        bill_amount=original_amount,

        # Actual cash/card/UPI/etc received.
        receive_amount=total_received,

        # Actual final payable after selected discounts.
        paid_amount=final_amount,

        change_amount=change_amount,

        payment_reference=(
            data.payment_reference
        ),

        notes=data.notes,

        offer_id=data.offer_id,

        offer_discount=round(
            offer_discount,
            2,
        ),

        # This remains ZERO unless
        # user explicitly selected wallet.
        wallet_discount=round(
            wallet_discount,
            2,
        ),
    )

    db.add(payment)

    try:

        # ====================================================
        # WALLET DEBIT
        # ====================================================
        #
        # THIS IS THE ONLY PLACE WHERE WALLET
        # IS ACTUALLY DEBITED.
        #
        # Preview NEVER debits wallet.
        #
        # ====================================================

        if (
            data.use_wallet is True
            and wallet_discount > 0
        ):

            if not customer_id:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "CRM customer is required "
                        "for wallet deduction"
                    ),
                )

            await debit_wallet(

                db=db,

                customer_id=customer_id,

                client_id=bill.client_id,

                branch_id=bill.branch_id,

                amount=wallet_discount,

                reference_type="BILL",

                reference_id=bill.id,

                notes=(
                    "CRM wallet contribution "
                    "against restaurant bill"
                ),
            )

        # ====================================================
        # OFFER USAGE
        # ====================================================

        if offer:

            offer.no_used = (
                int(offer.no_used or 0)
                + 1
            )

        # ====================================================
        # UPDATE BILL CUSTOMER
        # ========================================================

        if customer_id:

            bill.customer_id = customer_id

        # ====================================================
        # UPDATE BILL
        # ========================================================

        bill.paid_amount = final_amount

        bill.due_amount = 0.0

        bill.payment_status = (
            PaymentStatus.complete
        )

        bill.payment_method = payment_method

        bill.offer_id = data.offer_id

        bill.offer_discount = round(
            offer_discount,
            2,
        )

        # IMPORTANT:
        # This is zero when wallet was not selected.

        bill.wallet_discount = round(
            wallet_discount,
            2,
        )

        bill.final_amount = round(
            final_amount,
            2,
        )

        # ====================================================
        # COMMIT
        # ====================================================

        await db.commit()

        await db.refresh(payment)

        # ====================================================
        # CACHE
        # ========================================================

        await Cache.delete_pattern(
            f"dashboard:*:branch:{bill.branch_id}"
        )

        await Cache.delete(
            f"invoice:pdf:{bill.id}"
        )

        return payment

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Payment processing failed: {str(e)}"
            ),
        )

    except Exception as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Payment processing failed: {str(e)}"
            ),
        )