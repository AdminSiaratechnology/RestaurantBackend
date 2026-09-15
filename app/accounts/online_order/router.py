from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.exc import SQLAlchemyError

from app.db.config import SessionDep

from app.accounts.deps import (
    access_four,
)

from .model import (
    OnlinePlatform,
    OnlineOrderStatus,
)

from .schema import (
    OnlineOrderReject,
    OnlineOrderOut,
    OnlineOrderSummaryOut,
    PlatformStatusWebhook,
)

from .service import (
    accept_online_order_service,
    delivered_online_order_service,
    get_online_order_service,
    get_online_orders_service,
    get_online_order_summary_service,
    out_for_delivery_service,
    picked_up_online_order_service,
    process_platform_status_webhook,
    reject_online_order_service,
)


router = APIRouter(
    prefix="/online-orders",
    tags=["Online Orders"],
)


# =========================================================
# SUMMARY
# IMPORTANT: MUST COME BEFORE /{order_id}
# =========================================================

@router.get(
    "/summary",
    response_model=OnlineOrderSummaryOut,
)
async def get_summary(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_four),
):

    try:

        return await get_online_order_summary_service(
            db=db,
            current=current,
            branch_id=branch_id,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error",
        )


# =========================================================
# LIST ONLINE ORDERS
# =========================================================

@router.get(
    "/",
    response_model=list[OnlineOrderOut],
)
async def get_online_orders(
    db: SessionDep,
    branch_id: int | None = None,
    platform: OnlinePlatform | None = None,
    status: OnlineOrderStatus | None = None,
    current=Depends(access_four),
):

    try:

        return await get_online_orders_service(
            db=db,
            current=current,
            branch_id=branch_id,
            platform=platform,
            status=status,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "fetching online orders"
            ),
        )






# =========================================================
# PLATFORM STATUS WEBHOOK
# =========================================================

@router.post(
    "/webhook/{platform}",
)
async def platform_status_webhook(
    platform: OnlinePlatform,
    data: PlatformStatusWebhook,
    db: SessionDep,
):

    try:

        return await process_platform_status_webhook(
            db=db,
            platform=platform,
            data=data,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "processing platform webhook"
            ),
        )


# =========================================================
# GET SINGLE ORDER
# =========================================================

@router.get(
    "/{order_id}",
    response_model=OnlineOrderOut,
)
async def get_online_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await get_online_order_service(
            db=db,
            order_id=order_id,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error",
        )


# =========================================================
# ACCEPT
# =========================================================

@router.post(
    "/{order_id}/accept",
)
async def accept_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await accept_online_order_service(
            db=db,
            order_id=order_id,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while accepting order",
        )


# =========================================================
# REJECT
# =========================================================

@router.post(
    "/{order_id}/reject",
)
async def reject_order(
    order_id: int,
    data: OnlineOrderReject,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await reject_online_order_service(
            db=db,
            order_id=order_id,
            data=data,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while rejecting order",
        )


# =========================================================
# PICKED UP
# =========================================================

@router.post(
    "/{order_id}/picked-up",
)
async def picked_up_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await picked_up_online_order_service(
            db=db,
            order_id=order_id,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error",
        )


# =========================================================
# OUT FOR DELIVERY
# =========================================================

@router.post(
    "/{order_id}/out-for-delivery",
)
async def out_for_delivery(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await out_for_delivery_service(
            db=db,
            order_id=order_id,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error",
        )


# =========================================================
# DELIVERED
# =========================================================

@router.post(
    "/{order_id}/delivered",
)
async def delivered_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await delivered_online_order_service(
            db=db,
            order_id=order_id,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error",
        )


# =========================================================
# ACCEPT
# =========================================================

@router.patch(
    "/{order_id}/accept",
)
async def accept_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await accept_online_order_service(
            db=db,
            order_id=order_id,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while accepting order",
        )


# =========================================================
# REJECT
# =========================================================

@router.patch(
    "/{order_id}/reject",
)
async def reject_order(
    order_id: int,
    data: OnlineOrderReject,
    db: SessionDep,
    current=Depends(access_four),
):

    try:

        return await reject_online_order_service(
            db=db,
            order_id=order_id,
            data=data,
            current=current,
        )

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError:

        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while rejecting order",
        )