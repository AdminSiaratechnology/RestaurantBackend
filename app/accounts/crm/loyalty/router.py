"""
app/accounts/crm/loyalty/router.py

FastAPI router for Customer Loyalty.
"""

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.exc import SQLAlchemyError

from app.db.config import SessionDep

from app.accounts.customer.model import Customer

from app.accounts.deps import (
    access_one,
    get_client_if_accessible,
)

from app.accounts.crm.loyalty.schema import (
    LoyaltyAccountOut,
    LoyaltyTransactionOut,
    LoyaltyConversionOut,
    LoyaltyRedeemIn,
    LoyaltyRedeemOut,
)

from app.accounts.crm.loyalty.service import (
    calculate_customer_rank,
    get_loyalty_account,
    get_loyalty_transactions,
    convert_current_spend_to_loyalty_points,
    redeem_loyalty_points,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/crm/loyalty",
    tags=["CRM Loyalty"],
)


# ============================================================
# GET LOYALTY ACCOUNT
# ============================================================

@router.get(
    "/account",
    response_model=Optional[
        LoyaltyAccountOut
    ],
)
async def get_account(
    customer_id: int,
    db: SessionDep,
    current=Depends(access_one),
):

    try:

        customer = await db.get(
            Customer,
            customer_id,
        )

        if not customer:

            raise HTTPException(
                status_code=404,
                detail="Customer not found",
            )

        await get_client_if_accessible(
            customer.client_id,
            db,
            current,
        )

        account = await get_loyalty_account(
            db,
            customer_id,
        )

        if not account:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Loyalty account not found"
                ),
            )

        return account

    except HTTPException:

        raise

    except SQLAlchemyError as e:

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )


# ============================================================
# GET LOYALTY TRANSACTIONS
# ============================================================

@router.get(
    "/transactions",
    response_model=List[
        LoyaltyTransactionOut
    ],
)
async def list_transactions(
    customer_id: int,
    db: SessionDep,
    current=Depends(access_one),
):

    try:

        customer = await db.get(
            Customer,
            customer_id,
        )

        if not customer:

            raise HTTPException(
                status_code=404,
                detail="Customer not found",
            )

        await get_client_if_accessible(
            customer.client_id,
            db,
            current,
        )

        return await get_loyalty_transactions(
            db,
            customer_id,
        )

    except HTTPException:

        raise

    except SQLAlchemyError as e:

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )


# ============================================================
# RECALCULATE CUSTOMER LOYALTY
# ============================================================

@router.post(
    "/recalculate-loyalty/{customer_id}"
)
async def recalculate_customer_loyalty(
    customer_id: int,
    db: SessionDep,
    current=Depends(access_one),
):

    try:

        customer = await db.get(
            Customer,
            customer_id,
        )

        if not customer:

            raise HTTPException(
                status_code=404,
                detail="Customer not found",
            )

        # ====================================================
        # SECURITY
        # ====================================================

        await get_client_if_accessible(
            customer.client_id,
            db,
            current,
        )

        # ====================================================
        # CALCULATE
        # ====================================================

        rank = await calculate_customer_rank(
            db=db,
            customer=customer,
            branch_id=customer.branch_id,
        )

        # ====================================================
        # COMMIT
        # ====================================================

        await db.commit()

        await db.refresh(
            customer
        )

        return {
            "message": (
                "Customer loyalty recalculated"
            ),

            "customer_id": customer.id,

            "total_spend": float(
                customer.total_spend or 0.0
            ),

            "current_rank": (
                customer.current_rank
            ),

            "loyalty_points": float(
                customer.loyalty_points or 0.0
            ),
        }

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    except Exception as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Something went wrong: {str(e)}",
        )


# ============================================================
# CURRENT SPEND → LOYALTY POINTS
# ============================================================

@router.post(
    "/convert-current-spend/{customer_id}",
    response_model=LoyaltyConversionOut,
)
async def convert_current_spend(
    customer_id: int,
    db: SessionDep,
    current=Depends(access_one),
):

    try:

        # ====================================================
        # GET CUSTOMER
        # ====================================================

        customer = await db.get(
            Customer,
            customer_id,
        )

        if not customer:

            raise HTTPException(
                status_code=404,
                detail="Customer not found",
            )

        # ====================================================
        # SECURITY
        # ====================================================

        await get_client_if_accessible(
            customer.client_id,
            db,
            current,
        )

        # ====================================================
        # CONVERT CURRENT SPEND
        # ====================================================

        result = (
            await convert_current_spend_to_loyalty_points(
                db=db,
                customer_id=customer_id,
            )
        )

        # ====================================================
        # COMMIT
        # ====================================================

        await db.commit()

        return result

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    except Exception as e:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Something went wrong: {str(e)}",
        )


# ============================================================
# REDEEM LOYALTY POINTS
# ============================================================

@router.post(
    "/redeem",
    response_model=LoyaltyRedeemOut,
)
async def redeem_points_route(
    payload: LoyaltyRedeemIn,
    db: SessionDep,
    current=Depends(access_one),
):
    """
    Redeem customer loyalty points.

    Guarantees:
    - Decreases current_points_balance and increases total_points_redeemed.
    - Creates a LoyaltyTransaction record of type 'REDEEM'.
    - NEVER alters customer.total_spend or customer.current_rank.
    - NEVER alters CustomerVisitHistory.current_spend.
    """
    try:
        customer = await db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Customer not found",
            )

        await get_client_if_accessible(
            customer.client_id,
            db,
            current,
        )

        result = await redeem_loyalty_points(
            db=db,
            customer_id=payload.customer_id,
            points_to_redeem=payload.points,
            bill_id=payload.bill_id,
            description=payload.description,
        )

        await db.commit()

        return result

    except HTTPException:
        await db.rollback()
        raise

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Something went wrong: {str(e)}",
        )