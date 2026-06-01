from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from app.db.config import SessionDep
from app.accounts.deps import access_three, access_four, get_client_if_accessible
from app.accounts.order.model import Order
from app.accounts.enum import UserRole
from .schema import ALLOWED_STATUS_FLOW, OrderStatusUpdate   # if you created schema


router = APIRouter(prefix="/order-status", tags=["Order Status"])


@router.patch("/update_status/{order_id}")
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        # =========================
        # ✅ Fetch Order
        # =========================
        result = await db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(404, "Order not found")

        await get_client_if_accessible(order.client_id, db, current)

        # ✅ Branch security check for staff
        if current["role"] == UserRole.STAFF and order.branch_id != current["user"].branch_id:
            raise HTTPException(403, "Not allowed to access orders of another branch")

        current_status = order.status.lower()
        new_status = data.status.lower()

        # =========================
        # ✅ Validate Status
        # =========================
        if new_status not in ["pending", "preparing", "ready", "served"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid status value"
            )

        # =========================
        # ✅ Validate Transition
        # =========================
        # if new_status not in ALLOWED_STATUS_FLOW[current_status]:
        if (new_status != current_status and new_status not in ALLOWED_STATUS_FLOW[current_status]):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from '{current_status}' to '{new_status}'"
            )

        # =========================
        # ✅ Update Status
        # =========================
        order.status = new_status

        await db.commit()
        await db.refresh(order)

        return {
            "message": "Order status updated successfully",
            "order_id": order.id,
            "old_status": current_status,
            "new_status": new_status
        }

    # =========================
    # ✅ Exception Handling
    # =========================
    except HTTPException as e:
        await db.rollback()
        raise e

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



@router.patch("/cancel/{order_id}")
async def cancel_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:

        # =========================
        # ✅ Fetch Order
        # =========================
        result = await db.execute(
            select(Order).where(Order.id == order_id)
        )

        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        # =========================
        # ✅ Client Access Check
        # =========================
        await get_client_if_accessible(
            order.client_id,
            db,
            current
        )

        # ✅ Branch security check for staff
        if current["role"] == UserRole.STAFF and order.branch_id != current["user"].branch_id:
            raise HTTPException(403, "Not allowed to access orders of another branch")

        # =========================
        # ✅ Only Pending Orders Can Cancel
        # =========================
        if order.status.lower() != "pending":

            raise HTTPException(
                status_code=400,
                detail="Only pending orders can be cancelled"
            )

        # =========================
        # ✅ Change Status
        # =========================
        old_status = order.status

        order.status = "cancelled"

        await db.commit()
        await db.refresh(order)

        return {
            "success": True,
            "message": "Order cancelled successfully",
            "order_id": order.id,
            "old_status": old_status,
            "new_status": order.status
        }

    # =========================
    # ✅ Exception Handling
    # =========================
    except HTTPException as e:
        await db.rollback()
        raise e

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

