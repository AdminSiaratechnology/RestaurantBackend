# app/accounts/order_status/service.py

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.order.model import Order
from app.accounts.deps import get_client_if_accessible
from app.accounts.enum import UserRole
from .schema import ALLOWED_STATUS_FLOW


# =====================================
# UPDATE ORDER STATUS
# =====================================

async def update_order_status_service(
    db,
    order_id: int,
    data,
    current
):
    result = await db.execute(
        select(Order).where(
            Order.id == order_id
        )
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    await get_client_if_accessible(
        order.client_id,
        db,
        current
    )

    if (
        current["role"] == UserRole.STAFF
        and order.branch_id != current["user"].branch_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not allowed to access orders of another branch"
        )

    current_status = order.status.lower()
    new_status = data.status.lower()

    if new_status not in [
        "pending",
        "preparing",
        "ready",
        "served"
    ]:
        raise HTTPException(
            status_code=400,
            detail="Invalid status value"
        )

    if (
        new_status != current_status
        and new_status not in ALLOWED_STATUS_FLOW[current_status]
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from '{current_status}' to '{new_status}'"
        )

    order.status = new_status

    await db.commit()
    await db.refresh(order)

    return {
        "message": "Order status updated successfully",
        "order_id": order.id,
        "old_status": current_status,
        "new_status": new_status
    }


# =====================================
# CANCEL ORDER
# =====================================

async def cancel_order_service(
    db,
    order_id: int,
    current
):
    result = await db.execute(
        select(Order).where(
            Order.id == order_id
        )
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    await get_client_if_accessible(
        order.client_id,
        db,
        current
    )

    if (
        current["role"] == UserRole.STAFF
        and order.branch_id != current["user"].branch_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not allowed to access orders of another branch"
        )

    if order.status.lower() != "pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending orders can be cancelled"
        )

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