from datetime import (
    datetime,
    timezone,
)

from fastapi import HTTPException

from sqlalchemy import (
    delete,
    select,
    update,
)

from sqlalchemy.orm import (
    selectinload,
)

from app.accounts.order.model import (
    Order,
    OrderItem,
    OrderSource,
)

from app.accounts.deps import (
    get_client_if_accessible,
)

from app.accounts.enum import UserRole

from app.accounts.online_order.model import (
    OnlineOrderStatus,
)

from app.accounts.online_platforms.model import (
    OnlinePlatformConnection,
)

from app.accounts.online_platforms.registry import (
    PlatformRegistry,
)

from .schema import (
    ALLOWED_STATUS_FLOW,
)


# =========================================================
# GET ACTIVE PLATFORM CONNECTION
# =========================================================

async def get_platform_connection_for_order(
    db,
    order: Order,
):
    """
    Find the active platform connection for an online order.

    Match using:
    - client_id
    - branch_id
    - platform
    """

    online = order.online_order_detail

    if not online:

        raise HTTPException(
            status_code=400,
            detail="Online order detail not found",
        )

    result = await db.execute(
        select(OnlinePlatformConnection)
        .where(
            OnlinePlatformConnection.client_id
            == order.client_id,

            OnlinePlatformConnection.branch_id
            == order.branch_id,

            OnlinePlatformConnection.platform
            == online.platform,

            OnlinePlatformConnection.is_active.is_(True),
        )
    )

    connection = result.scalar_one_or_none()

    if not connection:

        platform_name = (
            online.platform.value
            if hasattr(online.platform, "value")
            else str(online.platform)
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Active platform connection not found "
                f"for '{platform_name}'"
            ),
        )

    return connection


# =========================================================
# SYNC READY STATUS TO PLATFORM
# =========================================================

async def sync_order_ready_to_platform(
    db,
    order: Order,
):
    """
    Sync kitchen READY status to online platform.

    Local database is NOT updated here.

    Flow:

        PlatformConnection
                ↓
        PlatformRegistry
                ↓
        Platform Adapter
                ↓
        update_order_status()
                ↓
        success / failure
    """

    online = order.online_order_detail

    if not online:

        raise HTTPException(
            status_code=400,
            detail="Online order detail not found",
        )

    # -----------------------------------------------------
    # GET PLATFORM CONNECTION
    # -----------------------------------------------------

    connection = await get_platform_connection_for_order(
        db=db,
        order=order,
    )

    # -----------------------------------------------------
    # PLATFORM NAME
    # -----------------------------------------------------

    platform_name = (
        online.platform.value
        if hasattr(online.platform, "value")
        else str(online.platform)
    )

    # -----------------------------------------------------
    # CREATE ADAPTER
    # -----------------------------------------------------

    try:

        adapter = PlatformRegistry.create(
            platform=platform_name,
            connection=connection,
            config={},
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to initialize platform adapter: "
                f"{str(exc)}"
            ),
        )

    # -----------------------------------------------------
    # CALL PLATFORM STATUS API
    # -----------------------------------------------------

    try:

        platform_response = (
            await adapter.update_order_status(
                platform_order_id=(
                    online.external_order_id
                ),
                status="ready_for_pickup",
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to sync order status "
                f"to {platform_name}: {str(exc)}"
            ),
        )

    # -----------------------------------------------------
    # VALIDATE PLATFORM RESPONSE
    # -----------------------------------------------------

    if not platform_response.get("success"):

        raise HTTPException(
            status_code=502,
            detail=(
                platform_response.get("message")
                or (
                    "Platform rejected the "
                    "status update request"
                )
            ),
        )

    return platform_response


# =========================================================
# UPDATE ORDER STATUS
# =========================================================

async def update_order_status_service(
    db,
    order_id: int,
    data,
    current,
):

    # -----------------------------------------------------
    # GET ORDER
    # -----------------------------------------------------

    result = await db.execute(
        select(Order)
        .options(
            selectinload(
                Order.online_order_detail
            )
        )
        .where(
            Order.id == order_id
        )
    )

    order = result.scalar_one_or_none()

    if not order:

        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # -----------------------------------------------------
    # ACCESS CHECK
    # -----------------------------------------------------

    await get_client_if_accessible(
        order.client_id,
        db,
        current,
    )

    if (
        current["role"] == UserRole.STAFF
        and order.branch_id
        != current["user"].branch_id
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Not allowed to access "
                "orders of another branch"
            ),
        )

    # -----------------------------------------------------
    # STATUS NORMALIZATION
    # -----------------------------------------------------

    current_status = (
        order.status or "pending"
    ).lower()

    new_status = (
        data.status or ""
    ).lower()

    # -----------------------------------------------------
    # VALIDATE STATUS
    # -----------------------------------------------------

    valid_statuses = {
        "pending",
        "accepted",
        "preparing",
        "ready",
        "served",
        "rejected",
        "cancelled",
    }

    if new_status not in valid_statuses:

        raise HTTPException(
            status_code=400,
            detail="Invalid status value",
        )

    # -----------------------------------------------------
    # VALIDATE FLOW
    # -----------------------------------------------------

    if (
        new_status != current_status
        and new_status
        not in ALLOWED_STATUS_FLOW.get(
            current_status,
            [],
        )
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition "
                f"from '{current_status}' "
                f"to '{new_status}'"
            ),
        )

    # -----------------------------------------------------
    # ONLINE ORDER VALIDATION
    # -----------------------------------------------------

    online = order.online_order_detail

    if online:

        # Online order must be accepted before preparation

        if (
            new_status == "preparing"
            and online.online_status
            != OnlineOrderStatus.ACCEPTED
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Online order must be accepted "
                    "before preparation"
                ),
            )

    # -----------------------------------------------------
    # ONLINE PLATFORM READY SYNC
    #
    # ONLY:
    #
    # source = online
    # preparing -> ready
    # -----------------------------------------------------

    platform_response = None

    should_sync_ready = (

        order.source == OrderSource.ONLINE

        and online is not None

        and current_status == "preparing"

        and new_status == "ready"

    )

    if should_sync_ready:

        platform_response = (
            await sync_order_ready_to_platform(
                db=db,
                order=order,
            )
        )

    # -----------------------------------------------------
    # UPDATE LOCAL RMS ORDER
    #
    # Only after successful platform sync
    # -----------------------------------------------------

    order.status = new_status

    # Also synchronize all order items to match the new order status
    await db.execute(
        update(OrderItem)
        .where(OrderItem.order_id == order.id)
        .values(order_status=new_status)
    )

    # -----------------------------------------------------
    # UPDATE ONLINE ORDER DETAIL
    # -----------------------------------------------------

    if should_sync_ready:

        online.online_status = (
            OnlineOrderStatus.READY_FOR_PICKUP
        )

        online.ready_at = (
            datetime.now(timezone.utc)
        )

    # -----------------------------------------------------
    # ONLINE ORDER SERVED VALIDATION
    # -----------------------------------------------------

    if online:

        if (
            new_status == "served"
            and online.online_status
            != OnlineOrderStatus.DELIVERED
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Online order must be marked "
                    "delivered before serving"
                ),
            )

    # -----------------------------------------------------
    # COMMIT
    # -----------------------------------------------------

    await db.commit()

    await db.refresh(order)

    # Trigger FCM order status notification safely
    try:
        from app.accounts.notification.service import NotificationService
        await NotificationService.send_order_status_update(
            db=db,
            order=order,
            old_status=current_status,
            new_status=new_status,
        )
    except Exception as notif_err:
        pass

    return {

        "success": True,

        "message": (
            "Order status updated successfully"
        ),

        "order_id": order.id,

        "old_status": current_status,

        "new_status": new_status,

        "online_status": (

            online.online_status.value

            if online

            else None

        ),

        "platform_synced": (
            platform_response is not None
        ),

        "platform_response": (
            platform_response
        ),

    }


# =========================================================
# CANCEL ORDER
# =========================================================

async def cancel_order_service(
    db,
    order_id: int,
    current,
):

    result = await db.execute(
        select(Order)
        .options(
            selectinload(
                Order.online_order_detail
            )
        )
        .where(
            Order.id == order_id
        )
    )

    order = result.scalar_one_or_none()

    if not order:

        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # -----------------------------------------------------
    # ACCESS CHECK
    # -----------------------------------------------------

    await get_client_if_accessible(
        order.client_id,
        db,
        current,
    )

    if (
        current["role"] == UserRole.STAFF
        and order.branch_id
        != current["user"].branch_id
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Not allowed to access "
                "orders of another branch"
            ),
        )

    # -----------------------------------------------------
    # ONLY PENDING ORDER CAN CANCEL
    # -----------------------------------------------------

    if (
        order.status or ""
    ).lower() != "pending":

        raise HTTPException(
            status_code=400,
            detail=(
                "Only pending orders can be cancelled"
            ),
        )

    old_status = order.status

    order.status = "cancelled"

    # -----------------------------------------------------
    # ONLINE ORDER SYNC
    # -----------------------------------------------------

    if order.online_order_detail:

        online = (
            order.online_order_detail
        )

        online.online_status = (
            OnlineOrderStatus.CANCELLED
        )

        online.cancelled_at = (
            datetime.now(timezone.utc)
        )

    # -----------------------------------------------------
    # CUSTOMER CRM CLEANUP
    # -----------------------------------------------------

    if order.customer_id:

        from app.accounts.crm.customer_history.model import (
            CustomerVisitHistory,
        )

        from app.accounts.customer.service import (
            recalculate_customer_crm,
        )

        await db.execute(

            delete(CustomerVisitHistory).where(

                CustomerVisitHistory.order_id
                == order.id

            )

        )

        await db.flush()

        await recalculate_customer_crm(
            db=db,
            customer_id=order.customer_id,
            branch_id=order.branch_id,
        )

    await db.commit()

    await db.refresh(order)

    # Trigger FCM cancellation notification safely
    try:
        from app.accounts.notification.service import NotificationService
        await NotificationService.send_order_status_update(
            db=db,
            order=order,
            old_status=old_status,
            new_status="cancelled",
        )
    except Exception as notif_err:
        pass

    return {

        "success": True,

        "message": (
            "Order cancelled successfully"
        ),

        "order_id": order.id,

        "old_status": old_status,

        "new_status": order.status,

        "online_status": (

            (
                order.online_order_detail
                .online_status
                .value
            )

            if order.online_order_detail

            else None

        ),

    }