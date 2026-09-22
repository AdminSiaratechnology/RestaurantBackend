import asyncio
import json
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select

from app.accounts.bill.model import Bill
from app.accounts.order.model import Order, OrderItem
from app.accounts.table_qr.model import RestaurantSession
from app.accounts.table_qr.schema import (
    PaymentVerifyOut,
    PublicOrderCreateReq,
    PublicPaymentFailureReq,
    QRResolutionOut,
    RazorpayInitiateOut,
    RazorpayPaymentVerifyReq,
    SessionCustomerAttachReq,
    SessionCustomerOut,
)
from app.accounts.table_qr.service import PublicCustomerQRService
from app.db.config import SessionDep

public_router = APIRouter(
    prefix="/public",
    tags=["Public Customer QR Ordering"],
)


async def get_session_from_header(
    db: SessionDep,
    x_restaurant_session: Optional[str] = Header(None, alias="X-Restaurant-Session"),
    session_token: Optional[str] = Query(None),
) -> RestaurantSession:
    token = x_restaurant_session or session_token
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Session header 'X-Restaurant-Session' or query parameter 'session_token' is required",
        )
    return await PublicCustomerQRService.get_session_by_token(db, token)


@public_router.get(
    "/qr/{token}",
    response_model=QRResolutionOut,
)
async def resolve_qr(
    token: str,
    db: SessionDep,
):
    return await PublicCustomerQRService.resolve_qr_and_start_session(
        db=db,
        token=token,
    )


@public_router.post(
    "/customer/session",
    response_model=SessionCustomerOut,
)
async def attach_customer_to_session(
    data: SessionCustomerAttachReq,
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
    x_restaurant_session: Optional[str] = Header(None, alias="X-Restaurant-Session"),
    session_token: Optional[str] = Query(None),
):
    res = await PublicCustomerQRService.attach_customer(
        db=db,
        session=session,
        data=data,
    )
    tok = x_restaurant_session or session_token or ""
    return {
        "session_token": tok,
        "customer_id": res["customer_id"],
        "name": res["name"],
        "phone": res["phone"],
        "email": res["email"],
    }


@public_router.get("/menu")
async def get_public_menu(
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
):
    return await PublicCustomerQRService.get_public_menu(
        db=db,
        session=session,
    )


@public_router.post("/order")
async def create_public_order(
    data: PublicOrderCreateReq,
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
):
    order = await PublicCustomerQRService.create_qr_order(
        db=db,
        session=session,
        data=data,
    )

    items_dto = [
        {
            "id": oi.id,
            "item_id": oi.item_id,
            "quantity": oi.quantity,
            "unit_price": oi.unit_price,
            "total_price": oi.total_price,
            "order_status": oi.order_status,
        }
        for oi in order.order_items
    ]

    return {
        "id": order.id,
        "branch_id": order.branch_id,
        "table_id": order.table_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "order_type": order.order_type.value if hasattr(order.order_type, "value") else str(order.order_type),
        "source": order.source.value if hasattr(order.source, "value") else str(order.source),
        "status": order.status,
        "total_amount": order.total_amount,
        "created_at": order.created_at,
        "items": items_dto,
    }


@public_router.get("/orders/{order_id}/status")
async def get_order_status(
    order_id: int,
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
):
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.restaurant_session_id == session.id,
        )
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found for this session",
        )

    bill_res = await db.execute(select(Bill).where(Bill.order_id == order.id))
    bill = bill_res.scalar_one_or_none()
    payment_status = "pending"
    if bill:
        payment_status = bill.payment_status.value if hasattr(bill.payment_status, "value") else str(bill.payment_status)

    return {
        "order_id": order.id,
        "status": order.status,
        "payment_status": payment_status,
        "session_status": session.status,
        "total_amount": order.total_amount,
        "updated_at": getattr(order, "updated_at", order.created_at),
    }


@public_router.websocket("/orders/{order_id}/ws")
async def order_status_websocket(
    websocket: WebSocket,
    order_id: int,
    session_token: str = Query(...),
):
    await websocket.accept()

    try:
        from app.db.config import get_db
        async for db in get_db():
            session = await PublicCustomerQRService.get_session_by_token(db, session_token)
            
            # Poll database for status changes cleanly over WebSocket
            last_status = None
            for _ in range(30):  # Maximum active poll duration per connection
                res = await db.execute(
                    select(Order).where(
                        Order.id == order_id,
                        Order.restaurant_session_id == session.id,
                    )
                )
                order = res.scalar_one_or_none()

                if order and order.status != last_status:
                    last_status = order.status
                    await websocket.send_json(
                        {
                            "event": "order_status_update",
                            "order_id": order.id,
                            "status": order.status,
                        }
                    )

                await asyncio.sleep(2)
            break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


@public_router.post(
    "/payment/initiate",
    response_model=RazorpayInitiateOut,
)
async def initiate_payment(
    order_id: int = Query(...),
    db: SessionDep = None,
    session: RestaurantSession = Depends(get_session_from_header),
):
    return await PublicCustomerQRService.initiate_payment(
        db=db,
        session=session,
        order_id=order_id,
    )


@public_router.post(
    "/payment/verify",
    response_model=PaymentVerifyOut,
)
async def verify_payment(
    data: RazorpayPaymentVerifyReq,
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
):
    return await PublicCustomerQRService.verify_payment(
        db=db,
        session=session,
        data=data,
    )


@public_router.post(
    "/payment/failure",
)
async def record_payment_failure(
    data: PublicPaymentFailureReq,
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
):
    return await PublicCustomerQRService.record_payment_failure(
        db=db,
        session=session,
        data=data,
    )



@public_router.post("/bill/request")
@public_router.post("/call-for-bill")
async def call_for_bill_endpoint(
    db: SessionDep,
    session: RestaurantSession = Depends(get_session_from_header),
):
    """
    Called when a customer at a table scans the QR code and clicks 'Call for Bill'.
    Validates that:
    1. Table session has placed orders.
    2. Active orders exist (not all cancelled/rejected).
    3. All active orders have reached 'served' status.
    Creates a BILL_REQUESTED notification in PostgreSQL scoped to the branch/client,
    dispatches FCM push to staff, and returns confirmation.
    """
    from app.accounts.table.model import Table
    from app.accounts.notification.service import NotificationService

    # 1. Get Table
    table = None
    if session.table_id:
        table = await db.get(Table, session.table_id)

    # 2. Get all orders for this session
    order_res = await db.execute(
        select(Order)
        .where(Order.restaurant_session_id == session.id)
        .order_by(Order.created_at.asc())
    )
    session_orders = list(order_res.scalars().all())

    if not session_orders:
        raise HTTPException(
            status_code=400,
            detail="Cannot request bill: No orders have been placed for this table session.",
        )

    active_orders = [o for o in session_orders if o.status not in ("cancelled", "rejected")]
    if not active_orders:
        raise HTTPException(
            status_code=400,
            detail="Cannot request bill: All placed orders have been cancelled or rejected.",
        )

    # Check if any active order is not yet served
    unserved_orders = [o for o in active_orders if o.status != "served"]
    if unserved_orders:
        unserved_str = ", ".join([f"Order #{o.id} ({o.status})" for o in unserved_orders])
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request bill yet: {unserved_str} not yet served. All orders must be served before requesting the bill.",
        )

    latest_served_order = active_orders[-1]

    # 3. Trigger bill requested notification to staff
    notif_res = await NotificationService.send_bill_requested(
        db=db,
        session=session,
        table=table,
        order=latest_served_order,
    )

    table_name = f"Table {table.name}" if table else f"Table {session.table_id}"

    return {
        "success": True,
        "message": f"Bill requested for {table_name}",
        "table_name": table_name,
        "order_id": latest_served_order.id,
        "notification_id": notif_res.get("notification_id"),
    }

