from fastapi import APIRouter, HTTPException

from sqlalchemy import select

from app.db.config import SessionDep

from app.accounts.payment.schema import (
    PaymentCreate,
    PaymentOut,
)

from app.accounts.payment.service import (
    make_payment_service,
    apply_offer_service,
    resolve_bill_customer,
)

from app.accounts.bill.model import Bill

from app.accounts.crm.wallet.service import (
    calculate_wallet_discount,
)

from app.accounts.offer.model import Offer

from app.accounts.offer.helper import (
    validate_and_calculate_offer,
    calculate_final_amount,
)


router = APIRouter(
    prefix="/payment",
    tags=["Payment"],
)


# ============================================================
# MAKE PAYMENT
# ============================================================


@router.post(
    "/pay",
    response_model=PaymentOut,
)
async def make_payment(
    data: PaymentCreate,
    db: SessionDep,
):

    try:

        return await make_payment_service(
            db,
            data,
        )

    except HTTPException:

        await db.rollback()

        raise

    except Exception:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Payment failed",
        )


# ============================================================
# APPLY OFFER
# ============================================================


@router.patch(
    "/apply-offer/{bill_id}",
)
async def apply_offer(
    bill_id: int,
    db: SessionDep,
    offer_id: int | None = None,
):

    try:

        return await apply_offer_service(
            db,
            bill_id,
            offer_id,
        )

    except HTTPException:

        raise

    except Exception:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to apply offer",
        )


# ============================================================
# WALLET PREVIEW
# ============================================================


@router.get(
    "/wallet-preview/{bill_id}",
)
async def wallet_preview(
    bill_id: int,
    db: SessionDep,
    offer_id: int | None = None,
    use_wallet: bool = False,
):

    # ========================================================
    # GET BILL
    # ========================================================

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:

        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    # ========================================================
    # RESOLVE CUSTOMER
    # ========================================================

    customer_id = await resolve_bill_customer(
        db,
        bill,
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
    # NO CUSTOMER
    # ========================================================

    if not customer_id:

        return {
            "bill_id": bill.id,

            "customer_id": None,

            "wallet_available": False,

            "wallet_balance": 0.0,

            "wallet_percent": 0.0,

            "max_wallet_discount": 0.0,

            "wallet_discount": 0.0,

            "original_amount": original_amount,

            "offer_discount": 0.0,

            "amount_after_offer": original_amount,

            # Wallet is not selected.
            "final_amount": original_amount,

            # No wallet available.
            "wallet_final_amount": original_amount,

            "use_wallet": False,

            "message": (
                "CRM customer is not attached "
                "to this order/bill"
            ),
        }

    # ========================================================
    # OFFER
    # ========================================================

    offer_discount = 0.0

    if offer_id:

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
    # WALLET INFORMATION
    # ========================================================
    #
    # IMPORTANT:
    #
    # This calculation DOES NOT debit wallet.
    #
    # It only tells us how much wallet contribution
    # is available.
    #
    # ========================================================

    wallet_info = (
        await calculate_wallet_discount(
            db=db,
            customer_id=customer_id,
            client_id=bill.client_id,
            branch_id=bill.branch_id,
            amount=amount_after_offer,
        )
    )

    wallet_balance = round(
        float(
            wallet_info.get(
                "wallet_balance",
                0.0,
            )
        ),
        2,
    )

    wallet_percent = round(
        float(
            wallet_info.get(
                "wallet_percent",
                0.0,
            )
        ),
        2,
    )

    max_wallet_discount = round(
        float(
            wallet_info.get(
                "max_wallet_discount",
                0.0,
            )
        ),
        2,
    )

    available_wallet_discount = round(
        float(
            wallet_info.get(
                "wallet_discount",
                0.0,
            )
        ),
        2,
    )

    if available_wallet_discount < 0:
        available_wallet_discount = 0.0

    # Never allow wallet contribution
    # above amount after offer.

    if available_wallet_discount > amount_after_offer:
        available_wallet_discount = amount_after_offer

    # ========================================================
    # WALLET FINAL AMOUNT
    # ========================================================
    #
    # This is only the hypothetical amount if wallet
    # is selected.
    #
    # It DOES NOT debit wallet.
    #
    # ========================================================

    wallet_final_amount = round(
        amount_after_offer
        - available_wallet_discount,
        2,
    )

    if wallet_final_amount < 0:
        wallet_final_amount = 0.0

    # ========================================================
    # ACTUAL PREVIEW FINAL AMOUNT
    # ========================================================
    #
    # If frontend has NOT selected wallet:
    #
    #     final_amount = amount_after_offer
    #
    # If frontend selected wallet:
    #
    #     final_amount = wallet_final_amount
    #
    # ========================================================

    if use_wallet is True:

        final_amount = wallet_final_amount

    else:

        final_amount = amount_after_offer

    # ========================================================
    # RESPONSE
    # ========================================================

    return {

        "bill_id": bill.id,

        "customer_id": customer_id,

        "wallet_available": (
            bool(
                wallet_info.get(
                    "wallet_available",
                    False,
                )
            )
            and available_wallet_discount > 0
        ),

        "wallet_balance": wallet_balance,

        "wallet_percent": wallet_percent,

        "max_wallet_discount": max_wallet_discount,

        # This is AVAILABLE wallet contribution.
        # It is NOT deducted here.
        "wallet_discount": available_wallet_discount,

        "original_amount": original_amount,

        "offer_discount": round(
            offer_discount,
            2,
        ),

        "amount_after_offer": (
            amount_after_offer
        ),

        # Actual amount based on current
        # use_wallet selection.
        "final_amount": final_amount,

        # Amount if wallet is selected.
        "wallet_final_amount": (
            wallet_final_amount
        ),

        "use_wallet": use_wallet,

        "message": (
            "Wallet contribution selected"
            if use_wallet and available_wallet_discount > 0
            else (
                "Wallet contribution available"
                if available_wallet_discount > 0
                else "No wallet contribution available"
            )
        ),
    }