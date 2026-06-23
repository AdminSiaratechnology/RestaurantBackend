# app/accounts/order_status/router.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.exc import SQLAlchemyError

from app.db.config import SessionDep

from app.accounts.deps import access_four

from .schema import OrderStatusUpdate

from .service import (
    update_order_status_service,
    cancel_order_service
)

router = APIRouter(
    prefix="/order-status",
    tags=["Order Status"]
)


# =====================================
# UPDATE ORDER STATUS
# =====================================

@router.patch("/update_status/{order_id}")
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        return await update_order_status_service(
            db=db,
            order_id=order_id,
            data=data,
            current=current
        )

    except HTTPException:
        await db.rollback()
        raise

    except SQLAlchemyError:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while updating order status"
        )

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unexpected error occurred"
        )


# =====================================
# CANCEL ORDER
# =====================================

@router.patch("/cancel/{order_id}")
async def cancel_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        return await cancel_order_service(
            db=db,
            order_id=order_id,
            current=current
        )

    except HTTPException:
        await db.rollback()
        raise

    except SQLAlchemyError:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while cancelling order"
        )

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unexpected error occurred"
        )