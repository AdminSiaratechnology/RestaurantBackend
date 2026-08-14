from fastapi import (
    APIRouter,
    HTTPException,
)

from app.db.config import SessionDep

from app.accounts.payment.schema import (
    PaymentCreate,
    PaymentOut,
)

from app.accounts.payment.service import (
    make_payment_service,
    apply_offer_service,
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

from sqlalchemy import select


router = APIRouter(
    prefix="/payment",
    tags=["Payment"],
)


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

        raise HTTPException(
            status_code=500,
            detail="Failed to apply offer",
        )


# =========================================================
# WALLET PREVIEW
# =========================================================

@router.get(
    "/wallet-preview/{bill_id}",
)
async def wallet_preview(
    bill_id: int,
    db: SessionDep,
    offer_id: int | None = None,
):

    result = await db.execute(
        select(Bill)
        .where(Bill.id == bill_id)
    )

    bill = result.scalar_one_or_none()

    if not bill:

        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    if not bill.customer_id:

        return {
            "bill_id": bill.id,
            "customer_id": None,
            "wallet_available": False,
            "wallet_balance": 0.0,
            "wallet_percent": 0.0,
            "max_wallet_discount": 0.0,
            "wallet_discount": 0.0,
            "amount_after_offer": bill.grand_total,
            "final_amount": bill.grand_total,
            "message": (
                "CRM customer is not attached "
                "to this bill"
            ),
        }

    # =====================================================
    # OFFER
    # =====================================================

    offer_discount = 0.0

    if offer_id:

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
    # WALLET
    # =====================================================

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

    final_amount = round(
        amount_after_offer - wallet_discount,
        2,
    )

    return {
        "bill_id": bill.id,
        "customer_id": bill.customer_id,

        "wallet_available": (
            wallet_discount > 0
        ),

        "wallet_balance": wallet_info[
            "wallet_balance"
        ],

        "wallet_percent": wallet_info[
            "wallet_percent"
        ],

        "max_wallet_discount": wallet_info[
            "max_wallet_discount"
        ],

        "wallet_discount": wallet_discount,

        "original_amount": bill.grand_total,

        "offer_discount": offer_discount,

        "amount_after_offer": amount_after_offer,

        "final_amount": final_amount,

        "message": (
            "Wallet discount available"
            if wallet_discount > 0
            else "No wallet discount available"
        ),
    }