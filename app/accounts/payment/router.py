# app/accounts/payment/router.py

from fastapi import (
    APIRouter,
    HTTPException
)

from app.db.config import SessionDep

from app.accounts.payment.schema import (
    PaymentCreate,
    PaymentOut
)

from app.accounts.payment.service import (
    make_payment_service,
    apply_offer_service
)

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
    try:

        return await make_payment_service(
            db,
            data
        )

    except HTTPException:
        await db.rollback()
        raise

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Payment failed"
        )


@router.patch(
    "/apply-offer/{bill_id}"
)
async def apply_offer(
    bill_id: int,
    db: SessionDep,
    offer_id: int | None = None
):
    try:

        return await apply_offer_service(
            db,
            bill_id,
            offer_id
        )

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to apply offer"
        )