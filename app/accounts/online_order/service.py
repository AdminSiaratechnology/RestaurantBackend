from datetime import datetime, timezone

from fastapi import HTTPException

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import (
    selectinload,
)

from app.accounts.order.model import (
    Order,
    OrderSource,
)

from app.accounts.deps import (
    get_client_if_accessible,
)

from app.accounts.enum import UserRole

from .model import (
    OnlineOrderDetail,
    OnlineOrderStatus,
)


from app.accounts.online_platforms.model import (
    OnlinePlatformConnection,
)

from app.accounts.online_platforms.registry import (
    PlatformRegistry,
)

from sqlalchemy.exc import IntegrityError

from app.accounts.webhooks.model import (
    WebhookEvent,
    WebhookEventStatus,
)

# =========================================================
# GET ONLINE ORDER WITH ACCESS CHECK
# =========================================================

async def get_online_order_with_access(
    db,
    order_id: int,
    current,
):

    result = await db.execute(
        select(Order)
        .options(
            selectinload(
                Order.order_items
            ).selectinload(
                "item"
            ),
            selectinload(
                Order.online_order_detail
            ),
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

    if (
        order.source != OrderSource.ONLINE
        or not order.online_order_detail
    ):

        raise HTTPException(
            status_code=400,
            detail="This is not an online order",
        )

    await get_client_if_accessible(
        order.client_id,
        db,
        current,
    )

    if (
        current["role"] == UserRole.STAFF
        and order.branch_id != current["user"].branch_id
    ):

        raise HTTPException(
            status_code=403,
            detail="Not allowed to access another branch",
        )

    return order






# =========================================================
# GET PLATFORM CONNECTION
# =========================================================

# async def get_platform_connection(
#     db,
#     order: Order,
#     online: OnlineOrderDetail,
# ):
#     """
#     Find the active platform connection for this order.

#     Matching:
#     - Client
#     - Branch
#     - Platform
#     """

#     result = await db.execute(
#         select(OnlinePlatformConnection)
#         .where(
#             OnlinePlatformConnection.client_id
#             == order.client_id,

#             OnlinePlatformConnection.branch_id
#             == order.branch_id,

#             OnlinePlatformConnection.platform
#             == online.platform,
#         )
#     )

#     connection = result.scalar_one_or_none()

#     if not connection:

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "No platform connection found for "
#                 f"platform '{online.platform.value}' "
#                 f"for this branch"
#             ),
#         )

#     return connection


async def get_platform_connection(
    db,
    order: Order,
    online: OnlineOrderDetail,
):

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

        raise HTTPException(
            status_code=400,
            detail=(
                f"Active platform connection not found "
                f"for '{online.platform.value}'"
            ),
        )

    return connection


# =========================================================
# SYNC ONLINE ORDER STATUS TO PLATFORM
# =========================================================

async def sync_online_order_status_to_platform(
    db,
    order: Order,
    online: OnlineOrderDetail,
    new_status: OnlineOrderStatus,
):
    """
    Sync online order status to external platform.

    Local database status is NOT updated here.
    Local status should only be updated after
    successful platform response.
    """

    # -----------------------------------------------------
    # GET PLATFORM CONNECTION
    # -----------------------------------------------------

    connection = await get_platform_connection(
        db=db,
        order=order,
        online=online,
    )

    # -----------------------------------------------------
    # GET PLATFORM NAME
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
    # CALL PLATFORM API
    # -----------------------------------------------------

    try:

        platform_response = (
            await adapter.update_order_status(
                platform_order_id=(
                    online.external_order_id
                ),
                status=new_status.value,
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Failed to sync status to "
                f"{platform_name}: {str(exc)}"
            ),
        )

    # -----------------------------------------------------
    # VALIDATE RESPONSE
    # -----------------------------------------------------

    if not platform_response:

        raise HTTPException(
            status_code=502,
            detail=(
                "Empty response received "
                "from platform"
            ),
        )

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

    return {
        "platform": platform_name,
        "response": platform_response,
    }



# =========================================================
# SERIALIZE ONLINE ORDER
# =========================================================

def serialize_online_order(order):

    online = order.online_order_detail

    return {

        "order_id": order.id,

        "client_id": order.client_id,

        "branch_id": order.branch_id,

        "customer_name": order.customer_name,

        "customer_phone": order.customer_phone,

        "notes": order.notes,

        "total_amount": order.total_amount or 0,

        "order_status": order.status,

        "platform": online.platform,

        "external_order_id": online.external_order_id,

        "external_order_number": (
            online.external_order_number
        ),

        "online_status": online.online_status,

        "rejection_reason": (
            online.rejection_reason
        ),

        "rejection_note": (
            online.rejection_note
        ),

        "received_at": online.received_at,

        "accepted_at": online.accepted_at,

        "ready_at": online.ready_at,

        "picked_up_at": online.picked_up_at,

        "out_for_delivery_at": (
            online.out_for_delivery_at
        ),

        "delivered_at": online.delivered_at,

        "items": [

            {
                "id": item.id,

                "item_id": item.item_id,

                "item_name": (
                    item.item.name
                    if item.item
                    else None
                ),

                "quantity": item.quantity,

                "unit_price": item.unit_price or 0,

                "total_price": item.total_price or 0,

                "order_status": item.order_status,
            }

            for item in order.order_items

        ],

    }


# =========================================================
# LIST ONLINE ORDERS
# =========================================================

async def get_online_orders_service(
    db,
    current,
    branch_id=None,
    platform=None,
    status=None,
):

    stmt = (
        select(Order)
        .join(
            OnlineOrderDetail,
            OnlineOrderDetail.order_id == Order.id,
        )
        .options(
            selectinload(
                Order.order_items
            ).selectinload(
                "item"
            ),
            selectinload(
                Order.online_order_detail
            ),
        )
        .where(
            Order.source == OrderSource.ONLINE
        )
        .order_by(
            Order.created_at.desc()
        )
    )

    if branch_id:

        stmt = stmt.where(
            Order.branch_id == branch_id
        )

    if platform:

        stmt = stmt.where(
            OnlineOrderDetail.platform == platform
        )

    if status:

        stmt = stmt.where(
            OnlineOrderDetail.online_status == status
        )

    result = await db.execute(stmt)

    orders = result.scalars().unique().all()

    accessible_orders = []

    for order in orders:

        try:

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
                continue

            accessible_orders.append(
                serialize_online_order(order)
            )

        except HTTPException:

            continue

    return accessible_orders


# =========================================================
# GET SINGLE ONLINE ORDER
# =========================================================

async def get_online_order_service(
    db,
    order_id,
    current,
):

    order = await get_online_order_with_access(
        db=db,
        order_id=order_id,
        current=current,
    )

    return serialize_online_order(order)


# =========================================================
# ACCEPT ONLINE ORDER
# =========================================================

# async def accept_online_order_service(
#     db,
#     order_id,
#     current,
# ):

#     order = await get_online_order_with_access(
#         db=db,
#         order_id=order_id,
#         current=current,
#     )

#     online = order.online_order_detail

#     if (
#         online.online_status
#         != OnlineOrderStatus.PENDING
#     ):

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Only pending online orders "
#                 "can be accepted"
#             ),
#         )

#     if order.status == "cancelled":

#         raise HTTPException(
#             status_code=400,
#             detail="Cancelled order cannot be accepted",
#         )

#     online.online_status = (
#         OnlineOrderStatus.ACCEPTED
#     )

#     online.accepted_at = datetime.now(
#         timezone.utc
#     )

#     # Order is now available for kitchen.
#     order.status = "pending"

#     await db.commit()

#     await db.refresh(order)

#     return {

#         "success": True,

#         "message": (
#             "Online order accepted and "
#             "sent to kitchen"
#         ),

#         "order_id": order.id,

#         "order_status": order.status,

#         "online_status": (
#             online.online_status.value
#         ),

#     }



# =========================================================
# ACCEPT ONLINE ORDER
# =========================================================

async def accept_online_order_service(
    db,
    order_id,
    current,
):

    # -----------------------------------------------------
    # GET ORDER
    # -----------------------------------------------------

    order = await get_online_order_with_access(
        db=db,
        order_id=order_id,
        current=current,
    )

    online = order.online_order_detail

    # -----------------------------------------------------
    # VALIDATE STATUS
    # -----------------------------------------------------

    if (
        online.online_status
        != OnlineOrderStatus.PENDING
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Only pending online orders "
                "can be accepted"
            ),
        )

    if order.status == "cancelled":

        raise HTTPException(
            status_code=400,
            detail=(
                "Cancelled order cannot be accepted"
            ),
        )

    # -----------------------------------------------------
    # GET PLATFORM CONNECTION
    # -----------------------------------------------------

    connection = await get_platform_connection(
        db=db,
        order=order,
        online=online,
    )

    # -----------------------------------------------------
    # CREATE PLATFORM ADAPTER
    # -----------------------------------------------------

    try:

        platform_name = (
            online.platform.value
            if hasattr(online.platform, "value")
            else str(online.platform)
        )

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
    # CALL PLATFORM ACCEPT API
    # -----------------------------------------------------

    try:

        platform_response = (
            await adapter.accept_order(
                platform_order_id=(
                    online.external_order_id
                ),
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to accept order on platform: "
                f"{str(exc)}"
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
                or
                "Platform rejected the accept request"
            ),
        )

    # -----------------------------------------------------
    # UPDATE LOCAL DATABASE
    # ONLY AFTER PLATFORM SUCCESS
    # -----------------------------------------------------

    online.online_status = (
        OnlineOrderStatus.ACCEPTED
    )

    online.accepted_at = datetime.now(
        timezone.utc
    )

    # Order is now available for kitchen
    order.status = "pending"

    await db.commit()

    await db.refresh(order)

    return {

        "success": True,

        "message": (
            "Online order accepted successfully "
            "and sent to kitchen"
        ),

        "order_id": order.id,

        "platform": platform_name,

        "external_order_id": (
            online.external_order_id
        ),

        "order_status": order.status,

        "online_status": (
            online.online_status.value
        ),

        "platform_response": (
            platform_response
        ),
    }



# =========================================================
# REJECT ONLINE ORDER
# =========================================================

# async def reject_online_order_service(
#     db,
#     order_id,
#     data,
#     current,
# ):

#     order = await get_online_order_with_access(
#         db=db,
#         order_id=order_id,
#         current=current,
#     )

#     online = order.online_order_detail

#     if (
#         online.online_status
#         != OnlineOrderStatus.PENDING
#     ):

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Only pending online orders "
#                 "can be rejected"
#             ),
#         )

#     online.online_status = (
#         OnlineOrderStatus.REJECTED
#     )

#     online.rejection_reason = data.reason

#     online.rejection_note = data.note

#     online.cancelled_at = datetime.now(
#         timezone.utc
#     )

#     order.status = "cancelled"

#     await db.commit()

#     return {

#         "success": True,

#         "message": "Online order rejected",

#         "order_id": order.id,

#         "order_status": order.status,

#         "online_status": (
#             online.online_status.value
#         ),

#     }
# =========================================================
# REJECT ONLINE ORDER
# =========================================================

async def reject_online_order_service(
    db,
    order_id,
    data,
    current,
):

    # -----------------------------------------------------
    # GET ORDER
    # -----------------------------------------------------

    order = await get_online_order_with_access(
        db=db,
        order_id=order_id,
        current=current,
    )

    online = order.online_order_detail

    # -----------------------------------------------------
    # VALIDATE STATUS
    # -----------------------------------------------------

    if (
        online.online_status
        != OnlineOrderStatus.PENDING
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Only pending online orders "
                "can be rejected"
            ),
        )

    # -----------------------------------------------------
    # GET PLATFORM CONNECTION
    # -----------------------------------------------------

    connection = await get_platform_connection(
        db=db,
        order=order,
        online=online,
    )

    # -----------------------------------------------------
    # CREATE PLATFORM ADAPTER
    # -----------------------------------------------------

    try:

        platform_name = (
            online.platform.value
            if hasattr(online.platform, "value")
            else str(online.platform)
        )

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
    # CALL PLATFORM REJECT API
    # -----------------------------------------------------

    try:

        platform_response = (
            await adapter.reject_order(
                platform_order_id=(
                    online.external_order_id
                ),
                reason=data.reason,
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to reject order on platform: "
                f"{str(exc)}"
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
                or
                "Platform rejected the reject request"
            ),
        )

    # -----------------------------------------------------
    # UPDATE LOCAL DATABASE
    # ONLY AFTER PLATFORM SUCCESS
    # -----------------------------------------------------

    online.online_status = (
        OnlineOrderStatus.REJECTED
    )

    online.rejection_reason = data.reason

    online.rejection_note = data.note

    online.cancelled_at = datetime.now(
        timezone.utc
    )

    order.status = "cancelled"

    await db.commit()

    await db.refresh(order)

    return {

        "success": True,

        "message": (
            "Online order rejected successfully"
        ),

        "order_id": order.id,

        "platform": platform_name,

        "external_order_id": (
            online.external_order_id
        ),

        "order_status": order.status,

        "online_status": (
            online.online_status.value
        ),

        "rejection_reason": (
            online.rejection_reason
        ),

        "rejection_note": (
            online.rejection_note
        ),

        "platform_response": (
            platform_response
        ),
    }


# =========================================================
# PICK UP ORDER
# =========================================================

# async def picked_up_online_order_service(
#     db,
#     order_id,
#     current,
# ):

#     order = await get_online_order_with_access(
#         db=db,
#         order_id=order_id,
#         current=current,
#     )

#     online = order.online_order_detail

#     if (
#         online.online_status
#         != OnlineOrderStatus.READY_FOR_PICKUP
#     ):

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Order must be ready for pickup "
#                 "before marking it picked up"
#             ),
#         )

#     online.online_status = (
#         OnlineOrderStatus.PICKED_UP
#     )

#     online.picked_up_at = datetime.now(
#         timezone.utc
#     )

#     await db.commit()

#     return {

#         "success": True,

#         "message": "Order marked as picked up",

#         "order_id": order.id,

#         "online_status": (
#             online.online_status.value
#         ),

#     }
# =========================================================
# PICK UP ORDER
# =========================================================

async def picked_up_online_order_service(
    db,
    order_id,
    current,
):

    # -----------------------------------------------------
    # GET ORDER
    # -----------------------------------------------------

    order = await get_online_order_with_access(
        db=db,
        order_id=order_id,
        current=current,
    )

    online = order.online_order_detail

    # -----------------------------------------------------
    # VALIDATE CURRENT STATUS
    # -----------------------------------------------------

    if (
        online.online_status
        != OnlineOrderStatus.READY_FOR_PICKUP
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Order must be ready for pickup "
                "before marking it picked up"
            ),
        )

    # -----------------------------------------------------
    # SYNC PLATFORM FIRST
    # -----------------------------------------------------

    sync_result = (
        await sync_online_order_status_to_platform(
            db=db,
            order=order,
            online=online,
            new_status=OnlineOrderStatus.PICKED_UP,
        )
    )

    # -----------------------------------------------------
    # UPDATE LOCAL DATABASE
    # ONLY AFTER PLATFORM SUCCESS
    # -----------------------------------------------------

    online.online_status = (
        OnlineOrderStatus.PICKED_UP
    )

    online.picked_up_at = (
        datetime.now(timezone.utc)
    )

    await db.commit()

    await db.refresh(order)

    return {

        "success": True,

        "message": (
            "Order marked as picked up successfully"
        ),

        "order_id": order.id,

        "platform": sync_result["platform"],

        "order_status": order.status,

        "online_status": (
            online.online_status.value
        ),

        "platform_response": (
            sync_result["response"]
        ),
    }

# =========================================================
# OUT FOR DELIVERY
# =========================================================

# async def out_for_delivery_service(
#     db,
#     order_id,
#     current,
# ):

#     order = await get_online_order_with_access(
#         db=db,
#         order_id=order_id,
#         current=current,
#     )

#     online = order.online_order_detail

#     if (
#         online.online_status
#         != OnlineOrderStatus.PICKED_UP
#     ):

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Order must be picked up "
#                 "before out for delivery"
#             ),
#         )

#     online.online_status = (
#         OnlineOrderStatus.OUT_FOR_DELIVERY
#     )

#     online.out_for_delivery_at = (
#         datetime.now(timezone.utc)
#     )

#     await db.commit()

#     return {

#         "success": True,

#         "message": (
#             "Order marked as out for delivery"
#         ),

#         "order_id": order.id,

#         "online_status": (
#             online.online_status.value
#         ),

#     }

# =========================================================
# OUT FOR DELIVERY
# =========================================================

async def out_for_delivery_service(
    db,
    order_id,
    current,
):

    # -----------------------------------------------------
    # GET ORDER
    # -----------------------------------------------------

    order = await get_online_order_with_access(
        db=db,
        order_id=order_id,
        current=current,
    )

    online = order.online_order_detail

    # -----------------------------------------------------
    # VALIDATE CURRENT STATUS
    # -----------------------------------------------------

    if (
        online.online_status
        != OnlineOrderStatus.PICKED_UP
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Order must be picked up "
                "before out for delivery"
            ),
        )

    # -----------------------------------------------------
    # SYNC PLATFORM FIRST
    # -----------------------------------------------------

    sync_result = (
        await sync_online_order_status_to_platform(
            db=db,
            order=order,
            online=online,
            new_status=(
                OnlineOrderStatus.OUT_FOR_DELIVERY
            ),
        )
    )

    # -----------------------------------------------------
    # UPDATE LOCAL DATABASE
    # ONLY AFTER PLATFORM SUCCESS
    # -----------------------------------------------------

    online.online_status = (
        OnlineOrderStatus.OUT_FOR_DELIVERY
    )

    online.out_for_delivery_at = (
        datetime.now(timezone.utc)
    )

    await db.commit()

    await db.refresh(order)

    return {

        "success": True,

        "message": (
            "Order marked as out for delivery "
            "successfully"
        ),

        "order_id": order.id,

        "platform": sync_result["platform"],

        "order_status": order.status,

        "online_status": (
            online.online_status.value
        ),

        "platform_response": (
            sync_result["response"]
        ),
    }


# =========================================================
# DELIVERED
# =========================================================

# async def delivered_online_order_service(
#     db,
#     order_id,
#     current,
# ):

#     order = await get_online_order_with_access(
#         db=db,
#         order_id=order_id,
#         current=current,
#     )

#     online = order.online_order_detail

#     if (
#         online.online_status
#         != OnlineOrderStatus.OUT_FOR_DELIVERY
#     ):

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Order must be out for delivery "
#                 "before marking delivered"
#             ),
#         )

#     online.online_status = (
#         OnlineOrderStatus.DELIVERED
#     )

#     online.delivered_at = datetime.now(
#         timezone.utc
#     )

#     # Final RMS status
#     order.status = "served"

#     await db.commit()

#     return {

#         "success": True,

#         "message": "Order delivered successfully",

#         "order_id": order.id,

#         "order_status": order.status,

#         "online_status": (
#             online.online_status.value
#         ),

#     }

# =========================================================
# DELIVERED
# =========================================================

async def delivered_online_order_service(
    db,
    order_id,
    current,
):

    # -----------------------------------------------------
    # GET ORDER
    # -----------------------------------------------------

    order = await get_online_order_with_access(
        db=db,
        order_id=order_id,
        current=current,
    )

    online = order.online_order_detail

    # -----------------------------------------------------
    # VALIDATE CURRENT STATUS
    # -----------------------------------------------------

    if (
        online.online_status
        != OnlineOrderStatus.OUT_FOR_DELIVERY
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Order must be out for delivery "
                "before marking delivered"
            ),
        )

    # -----------------------------------------------------
    # SYNC PLATFORM FIRST
    # -----------------------------------------------------

    sync_result = (
        await sync_online_order_status_to_platform(
            db=db,
            order=order,
            online=online,
            new_status=OnlineOrderStatus.DELIVERED,
        )
    )

    # -----------------------------------------------------
    # UPDATE LOCAL DATABASE
    # ONLY AFTER PLATFORM SUCCESS
    # -----------------------------------------------------

    online.online_status = (
        OnlineOrderStatus.DELIVERED
    )

    online.delivered_at = (
        datetime.now(timezone.utc)
    )

    # Final RMS status

    order.status = "served"

    await db.commit()

    await db.refresh(order)

    return {

        "success": True,

        "message": (
            "Order delivered successfully"
        ),

        "order_id": order.id,

        "platform": sync_result["platform"],

        "order_status": order.status,

        "online_status": (
            online.online_status.value
        ),

        "platform_response": (
            sync_result["response"]
        ),
    }


# =========================================================
# ONLINE ORDER SUMMARY
# =========================================================

async def get_online_order_summary_service(
    db,
    current,
    branch_id=None,
):

    stmt = (
        select(
            OnlineOrderDetail.online_status,
            func.count(
                OnlineOrderDetail.id
            ),
        )
        .join(
            Order,
            Order.id
            == OnlineOrderDetail.order_id,
        )
        .where(
            Order.source == OrderSource.ONLINE
        )
        .group_by(
            OnlineOrderDetail.online_status
        )
    )

    if branch_id:

        stmt = stmt.where(
            Order.branch_id == branch_id
        )

    result = await db.execute(stmt)

    rows = result.all()

    summary = {

        "pending": 0,

        "accepted": 0,

        "ready_for_pickup": 0,

        "picked_up": 0,

        "out_for_delivery": 0,

        "delivered": 0,

        "rejected": 0,

        "cancelled": 0,

    }

    for status, count in rows:

        status_value = (
            status.value
            if hasattr(status, "value")
            else status
        )

        if status_value in summary:

            summary[status_value] = count

    return summary




# =========================================================
# NORMALIZE PLATFORM STATUS
# =========================================================

def normalize_platform_status(
    status: str,
) -> OnlineOrderStatus:

    normalized = (
        status
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {

        "pending": OnlineOrderStatus.PENDING,

        "accepted": OnlineOrderStatus.ACCEPTED,

        "confirmed": OnlineOrderStatus.ACCEPTED,

        "ready": OnlineOrderStatus.READY_FOR_PICKUP,

        "ready_for_pickup":
            OnlineOrderStatus.READY_FOR_PICKUP,

        "picked_up":
            OnlineOrderStatus.PICKED_UP,

        "pickedup":
            OnlineOrderStatus.PICKED_UP,

        "out_for_delivery":
            OnlineOrderStatus.OUT_FOR_DELIVERY,

        "outfordelivery":
            OnlineOrderStatus.OUT_FOR_DELIVERY,

        "delivered":
            OnlineOrderStatus.DELIVERED,

        "cancelled":
            OnlineOrderStatus.CANCELLED,

        "canceled":
            OnlineOrderStatus.CANCELLED,

        "rejected":
            OnlineOrderStatus.REJECTED,
    }

    if normalized not in aliases:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported platform status: "
                f"'{status}'"
            ),
        )

    return aliases[normalized]




# =========================================================
# CHECK STATUS TRANSITION
# =========================================================

def validate_platform_status_transition(
    current_status: OnlineOrderStatus,
    new_status: OnlineOrderStatus,
):

    # Same status webhook = safe / idempotent
    if current_status == new_status:

        return "duplicate"

    allowed_transitions = {

        OnlineOrderStatus.PENDING: [

            OnlineOrderStatus.ACCEPTED,

            OnlineOrderStatus.REJECTED,

            OnlineOrderStatus.CANCELLED,
        ],

        OnlineOrderStatus.ACCEPTED: [

            OnlineOrderStatus.READY_FOR_PICKUP,

            OnlineOrderStatus.CANCELLED,
        ],

        OnlineOrderStatus.READY_FOR_PICKUP: [

            OnlineOrderStatus.PICKED_UP,

            OnlineOrderStatus.CANCELLED,
        ],

        OnlineOrderStatus.PICKED_UP: [

            OnlineOrderStatus.OUT_FOR_DELIVERY,

            OnlineOrderStatus.CANCELLED,
        ],

        OnlineOrderStatus.OUT_FOR_DELIVERY: [

            OnlineOrderStatus.DELIVERED,

            OnlineOrderStatus.CANCELLED,
        ],

        OnlineOrderStatus.DELIVERED: [],

        OnlineOrderStatus.REJECTED: [],

        OnlineOrderStatus.CANCELLED: [],
    }

    if new_status not in allowed_transitions.get(
        current_status,
        [],
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid platform status transition "
                f"from '{current_status.value}' "
                f"to '{new_status.value}'"
            ),
        )

    return "valid"


# =========================================================
# PLATFORM STATUS WEBHOOK SERVICE
# =========================================================

# async def process_platform_status_webhook(
#     db,
#     platform,
#     data,
# ):

#     # -----------------------------------------------------
#     # NORMALIZE PLATFORM
#     # -----------------------------------------------------

#     platform_value = (
#         platform.value
#         if hasattr(platform, "value")
#         else str(platform).lower()
#     )

#     # -----------------------------------------------------
#     # FIND ONLINE ORDER
#     # -----------------------------------------------------

#     result = await db.execute(
#         select(OnlineOrderDetail)
#         .options(
#             selectinload(
#                 OnlineOrderDetail.order
#             )
#         )
#         .where(
#             OnlineOrderDetail.platform == platform_value,
#             OnlineOrderDetail.external_order_id
#             == data.external_order_id,
#         )
#     )

#     online = result.scalar_one_or_none()

#     if not online:

#         raise HTTPException(
#             status_code=404,
#             detail=(
#                 "Online order not found for "
#                 f"external_order_id "
#                 f"'{data.external_order_id}'"
#             ),
#         )

#     order = online.order

#     # -----------------------------------------------------
#     # NORMALIZE STATUS
#     # -----------------------------------------------------

#     new_status = normalize_platform_status(
#         data.status
#     )

#     current_status = online.online_status

#     # -----------------------------------------------------
#     # IDEMPOTENCY / VALIDATE TRANSITION
#     # -----------------------------------------------------

#     transition_result = (
#         validate_platform_status_transition(
#             current_status=current_status,
#             new_status=new_status,
#         )
#     )

#     # -----------------------------------------------------
#     # DUPLICATE WEBHOOK
#     # -----------------------------------------------------

#     if transition_result == "duplicate":

#         return {

#             "success": True,

#             "duplicate": True,

#             "message": (
#                 "Webhook already processed"
#             ),

#             "order_id": order.id,

#             "external_order_id": (
#                 online.external_order_id
#             ),

#             "online_status": (
#                 online.online_status.value
#             ),
#         }

#     # -----------------------------------------------------
#     # UPDATE ONLINE STATUS
#     # -----------------------------------------------------

#     online.online_status = new_status

#     now = datetime.now(timezone.utc)

#     # -----------------------------------------------------
#     # STATUS TIMESTAMPS
#     # -----------------------------------------------------

#     if new_status == OnlineOrderStatus.ACCEPTED:

#         online.accepted_at = now

#         order.status = "pending"

#     elif (
#         new_status
#         == OnlineOrderStatus.READY_FOR_PICKUP
#     ):

#         online.ready_at = now

#         # Kitchen order should already be ready,
#         # but platform is source of truth here.
#         order.status = "ready"

#     elif new_status == OnlineOrderStatus.PICKED_UP:

#         online.picked_up_at = now

#     elif (
#         new_status
#         == OnlineOrderStatus.OUT_FOR_DELIVERY
#     ):

#         online.out_for_delivery_at = now

#     elif new_status == OnlineOrderStatus.DELIVERED:

#         online.delivered_at = now

#         order.status = "served"

#     elif new_status == OnlineOrderStatus.REJECTED:

#         online.cancelled_at = now

#         order.status = "cancelled"

#     elif new_status == OnlineOrderStatus.CANCELLED:

#         online.cancelled_at = now

#         order.status = "cancelled"

#     # -----------------------------------------------------
#     # STORE WEBHOOK METADATA
#     # -----------------------------------------------------

#     existing_metadata = (
#         online.platform_metadata or {}
#     )

#     existing_metadata["last_webhook"] = {

#         "event_id": data.event_id,

#         "status": new_status.value,

#         "metadata": data.metadata,

#         "received_at": now.isoformat(),
#     }

#     online.platform_metadata = existing_metadata

#     # -----------------------------------------------------
#     # COMMIT
#     # -----------------------------------------------------

#     await db.commit()

#     await db.refresh(online)

#     return {

#         "success": True,

#         "duplicate": False,

#         "message": (
#             "Platform webhook processed successfully"
#         ),

#         "order_id": order.id,

#         "platform": platform_value,

#         "external_order_id": (
#             online.external_order_id
#         ),

#         "old_status": current_status.value,

#         "new_status": new_status.value,

#         "order_status": order.status,
#     }



# async def process_platform_status_webhook(
#     db,
#     platform,
#     data,
# ):

#     # -----------------------------------------------------
#     # NORMALIZE PLATFORM
#     # -----------------------------------------------------

#     platform_value = (

#         platform.value

#         if hasattr(platform, "value")

#         else str(platform).lower()

#     )

#     # -----------------------------------------------------
#     # DATABASE IDEMPOTENCY CHECK
#     # -----------------------------------------------------

#     webhook_event, is_duplicate = (
#         await create_webhook_event(

#             db=db,

#             platform=platform_value,

#             data=data,
#         )
#     )

#     # -----------------------------------------------------
#     # DUPLICATE EVENT
#     # -----------------------------------------------------

#     if is_duplicate:

#         return {

#             "success": True,

#             "duplicate": True,

#             "message":
#                 "Webhook event already received",

#             "event_id": data.event_id,

#             "event_status": (

#                 webhook_event.status.value

#                 if webhook_event

#                 else None

#             ),
#         }

#     try:

#         # -------------------------------------------------
#         # FIND ONLINE ORDER
#         # -------------------------------------------------

#         result = await db.execute(

#             select(OnlineOrderDetail)

#             .options(

#                 selectinload(
#                     OnlineOrderDetail.order
#                 )

#             )

#             .where(

#                 OnlineOrderDetail.platform
#                 == platform_value,

#                 OnlineOrderDetail.external_order_id
#                 == data.external_order_id,
#             )

#         )

#         online = result.scalar_one_or_none()

#         if not online:

#             webhook_event.status = (
#                 WebhookEventStatus.FAILED
#             )

#             webhook_event.error_message = (
#                 "Online order not found"
#             )

#             await db.commit()

#             raise HTTPException(
#                 status_code=404,
#                 detail="Online order not found",
#             )

#         order = online.order

#         webhook_event.order_id = order.id

#         # -------------------------------------------------
#         # NORMALIZE STATUS
#         # -------------------------------------------------

#         new_status = (
#             normalize_platform_status(
#                 data.status
#             )
#         )

#         current_status = (
#             online.online_status
#         )

#         # -------------------------------------------------
#         # VALIDATE STATUS TRANSITION
#         # -------------------------------------------------

#         transition_result = (

#             validate_platform_status_transition(

#                 current_status=current_status,

#                 new_status=new_status,
#             )

#         )

#         # -------------------------------------------------
#         # DUPLICATE STATUS
#         # -------------------------------------------------

#         if transition_result == "duplicate":

#             webhook_event.status = (
#                 WebhookEventStatus.PROCESSED
#             )

#             webhook_event.processed_at = (
#                 datetime.now(timezone.utc)
#             )

#             await db.commit()

#             return {

#                 "success": True,

#                 "duplicate": True,

#                 "message":
#                     "Order already has this status",

#                 "event_id": data.event_id,

#                 "order_id": order.id,

#                 "online_status":
#                     online.online_status.value,
#             }

#         # -------------------------------------------------
#         # UPDATE ONLINE STATUS
#         # -------------------------------------------------

#         online.online_status = new_status

#         now = datetime.now(timezone.utc)

#         # -------------------------------------------------
#         # TIMESTAMP + RMS STATUS SYNC
#         # -------------------------------------------------

#         if new_status == OnlineOrderStatus.ACCEPTED:

#             online.accepted_at = now

#             order.status = "pending"

#         elif (
#             new_status
#             == OnlineOrderStatus.READY_FOR_PICKUP
#         ):

#             online.ready_at = now

#             order.status = "ready"

#         elif new_status == OnlineOrderStatus.PICKED_UP:

#             online.picked_up_at = now

#         elif (
#             new_status
#             == OnlineOrderStatus.OUT_FOR_DELIVERY
#         ):

#             online.out_for_delivery_at = now

#         elif new_status == OnlineOrderStatus.DELIVERED:

#             online.delivered_at = now

#             order.status = "served"

#         elif new_status == OnlineOrderStatus.REJECTED:

#             online.cancelled_at = now

#             order.status = "cancelled"

#         elif new_status == OnlineOrderStatus.CANCELLED:

#             online.cancelled_at = now

#             order.status = "cancelled"

#         # -------------------------------------------------
#         # SAVE LAST WEBHOOK INFO
#         # -------------------------------------------------

#         existing_metadata = (
#             online.platform_metadata or {}
#         )

#         existing_metadata["last_webhook"] = {

#             "event_id": data.event_id,

#             "event_type": data.event_type,

#             "status": new_status.value,

#             "metadata": data.metadata,

#             "received_at": now.isoformat(),
#         }

#         online.platform_metadata = (
#             existing_metadata
#         )

#         # -------------------------------------------------
#         # MARK EVENT PROCESSED
#         # -------------------------------------------------

#         webhook_event.status = (
#             WebhookEventStatus.PROCESSED
#         )

#         webhook_event.processed_at = now

#         # -------------------------------------------------
#         # COMMIT EVERYTHING TOGETHER
#         # -------------------------------------------------

#         await db.commit()

#         await db.refresh(online)

#         return {

#             "success": True,

#             "duplicate": False,

#             "message":
#                 "Platform webhook processed successfully",

#             "event_id": data.event_id,

#             "order_id": order.id,

#             "platform": platform_value,

#             "external_order_id":
#                 online.external_order_id,

#             "old_status":
#                 current_status.value,

#             "new_status":
#                 new_status.value,

#             "order_status":
#                 order.status,
#         }

#     except HTTPException:

#         raise

#     except Exception as exc:

#         webhook_event.status = (
#             WebhookEventStatus.FAILED
#         )

#         webhook_event.error_message = str(exc)

#         await db.commit()

#         raise

async def process_platform_status_webhook(
    db,
    platform,
    data,
):

    # -----------------------------------------------------
    # NORMALIZE PLATFORM
    # -----------------------------------------------------

    platform_value = (

        platform.value

        if hasattr(platform, "value")

        else str(platform).lower()

    )

    # -----------------------------------------------------
    # DATABASE IDEMPOTENCY CHECK
    # -----------------------------------------------------

    webhook_event, is_duplicate = (
        await create_webhook_event(

            db=db,

            platform=platform_value,

            data=data,
        )
    )

    # -----------------------------------------------------
    # DUPLICATE EVENT
    # -----------------------------------------------------

    if is_duplicate:

        return {

            "success": True,

            "duplicate": True,

            "message":
                "Webhook event already received",

            "event_id": data.event_id,

            "event_status": (

                webhook_event.status.value

                if webhook_event

                else None

            ),
        }

    try:

        # -------------------------------------------------
        # FIND ONLINE ORDER
        # -------------------------------------------------

        result = await db.execute(

            select(OnlineOrderDetail)

            .options(

                selectinload(
                    OnlineOrderDetail.order
                )

            )

            .where(

                OnlineOrderDetail.platform
                == platform_value,

                OnlineOrderDetail.external_order_id
                == data.external_order_id,
            )

        )

        online = result.scalar_one_or_none()

        if not online:

            webhook_event.status = (
                WebhookEventStatus.FAILED
            )

            webhook_event.error_message = (
                "Online order not found"
            )

            await db.commit()

            raise HTTPException(
                status_code=404,
                detail="Online order not found",
            )

        order = online.order

        webhook_event.order_id = order.id

        # -------------------------------------------------
        # NORMALIZE STATUS
        # -------------------------------------------------

        new_status = (
            normalize_platform_status(
                data.status
            )
        )

        current_status = (
            online.online_status
        )

        # -------------------------------------------------
        # VALIDATE STATUS TRANSITION
        # -------------------------------------------------

        transition_result = (

            validate_platform_status_transition(

                current_status=current_status,

                new_status=new_status,
            )

        )

        # -------------------------------------------------
        # DUPLICATE STATUS
        # -------------------------------------------------

        if transition_result == "duplicate":

            webhook_event.status = (
                WebhookEventStatus.PROCESSED
            )

            webhook_event.processed_at = (
                datetime.now(timezone.utc)
            )

            await db.commit()

            return {

                "success": True,

                "duplicate": True,

                "message":
                    "Order already has this status",

                "event_id": data.event_id,

                "order_id": order.id,

                "online_status":
                    online.online_status.value,
            }

        # -------------------------------------------------
        # UPDATE ONLINE STATUS
        # -------------------------------------------------

        online.online_status = new_status

        now = datetime.now(timezone.utc)

        # -------------------------------------------------
        # TIMESTAMP + RMS STATUS SYNC
        # -------------------------------------------------

        if new_status == OnlineOrderStatus.ACCEPTED:

            online.accepted_at = now

            order.status = "pending"

        elif (
            new_status
            == OnlineOrderStatus.READY_FOR_PICKUP
        ):

            online.ready_at = now

            order.status = "ready"

        elif new_status == OnlineOrderStatus.PICKED_UP:

            online.picked_up_at = now

        elif (
            new_status
            == OnlineOrderStatus.OUT_FOR_DELIVERY
        ):

            online.out_for_delivery_at = now

        elif new_status == OnlineOrderStatus.DELIVERED:

            online.delivered_at = now

            order.status = "served"

        elif new_status == OnlineOrderStatus.REJECTED:

            online.cancelled_at = now

            order.status = "cancelled"

        elif new_status == OnlineOrderStatus.CANCELLED:

            online.cancelled_at = now

            order.status = "cancelled"

        # -------------------------------------------------
        # SAVE LAST WEBHOOK INFO
        # -------------------------------------------------

        existing_metadata = (
            online.platform_metadata or {}
        )

        existing_metadata["last_webhook"] = {

            "event_id": data.event_id,

            "event_type": data.event_type,

            "status": new_status.value,

            "metadata": data.metadata,

            "received_at": now.isoformat(),
        }

        online.platform_metadata = (
            existing_metadata
        )

        # -------------------------------------------------
        # MARK EVENT PROCESSED
        # -------------------------------------------------

        webhook_event.status = (
            WebhookEventStatus.PROCESSED
        )

        webhook_event.processed_at = now

        # -------------------------------------------------
        # COMMIT EVERYTHING TOGETHER
        # -------------------------------------------------

        await db.commit()

        await db.refresh(online)

        return {

            "success": True,

            "duplicate": False,

            "message":
                "Platform webhook processed successfully",

            "event_id": data.event_id,

            "order_id": order.id,

            "platform": platform_value,

            "external_order_id":
                online.external_order_id,

            "old_status":
                current_status.value,

            "new_status":
                new_status.value,

            "order_status":
                order.status,
        }

    except HTTPException:

        raise

    except Exception as exc:

        webhook_event.status = (
            WebhookEventStatus.FAILED
        )

        webhook_event.error_message = str(exc)

        await db.commit()

        raise


# =========================================================
# CREATE WEBHOOK EVENT
# DATABASE LEVEL IDEMPOTENCY
# =========================================================

async def create_webhook_event(
    db,
    platform: str,
    data,
):

    event = WebhookEvent(

        platform=platform,

        event_id=data.event_id,

        event_type=data.event_type,

        external_order_id=data.external_order_id,

        status=WebhookEventStatus.PROCESSING,

        payload={

            "external_order_id":
                data.external_order_id,

            "status":
                data.status,

            "event_type":
                data.event_type,

            "metadata":
                data.metadata,
        },
    )

    try:

        db.add(event)

        await db.flush()

        return event, False

    except IntegrityError:

        await db.rollback()

        result = await db.execute(

            select(WebhookEvent).where(

                WebhookEvent.platform == platform,

                WebhookEvent.event_id
                == data.event_id,
            )

        )

        existing_event = (
            result.scalar_one_or_none()
        )

        return existing_event, True




# =========================================================
# CREATE WEBHOOK EVENT
# DATABASE LEVEL IDEMPOTENCY
# =========================================================

async def create_webhook_event(
    db,
    platform: str,
    data,
):

    event = WebhookEvent(

        platform=platform,

        event_id=data.event_id,

        event_type=data.event_type,

        external_order_id=data.external_order_id,

        status=WebhookEventStatus.PROCESSING,

        payload={

            "external_order_id":
                data.external_order_id,

            "status":
                data.status,

            "event_type":
                data.event_type,

            "metadata":
                data.metadata,
        },
    )

    try:

        db.add(event)

        await db.flush()

        return event, False

    except IntegrityError:

        await db.rollback()

        result = await db.execute(

            select(WebhookEvent).where(

                WebhookEvent.platform == platform,

                WebhookEvent.event_id
                == data.event_id,
            )

        )

        existing_event = (
            result.scalar_one_or_none()
        )

        return existing_event, True