# app/accounts/notification/router.py

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.deps import access_four, access_one
from app.accounts.enum import UserRole
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.notification.model import (
    CustomerNotificationPreference,
    DeviceToken,
    Notification,
    NotificationType,
)
from app.accounts.notification.schema import (
    CustomerNotificationPreferenceReq,
    CustomerNotificationPreferenceResponse,
    DeviceTokenRegisterReq,
    NotificationListResponse,
    NotificationResponse,
    PublicDeviceTokenRegisterReq,
    SendAnnouncementReq,
    SendNewMenuReq,
    SendOfferNotificationReq,
)
from app.accounts.notification.service import NotificationService
from app.accounts.table_qr.service import PublicCustomerQRService
from app.db.config import SessionDep

# =============================================================================
# PUBLIC NOTIFICATION ROUTER (QR Ordering App)
# =============================================================================

public_notification_router = APIRouter(
    prefix="/public/notifications",
    tags=["Public Notifications"],
)


@public_notification_router.post("/device-token")
async def register_public_device_token(
    data: PublicDeviceTokenRegisterReq,
    db: SessionDep,
    x_restaurant_session: Optional[str] = Header(None, alias="X-Restaurant-Session"),
):
    """
    Registers an FCM device token for an anonymous or customer-attached QR session.
    Does NOT require a staff or user account.
    """
    session_token = data.session_token or x_restaurant_session
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Session token required via header 'X-Restaurant-Session' or payload",
        )

    session = await PublicCustomerQRService.get_session_by_token(db, session_token)

    device_token = await NotificationService.register_or_update_device_token(
        db=db,
        token=data.token,
        platform=data.platform,
        client_id=session.client_id,
        branch_id=session.branch_id,
        customer_id=session.customer_id,
        qr_session_id=session.id,
        device_id=data.device_id,
    )

    return {
        "success": True,
        "message": "FCM device token registered for QR session",
        "device_token_id": device_token.id,
        "qr_session_id": session.id,
        "is_active": device_token.is_active,
    }


@public_notification_router.get("", response_model=NotificationListResponse)
async def get_public_session_notifications(
    db: SessionDep,
    x_restaurant_session: Optional[str] = Header(None, alias="X-Restaurant-Session"),
    session_token: Optional[str] = Query(None),
):
    """Retrieves notification history for the current QR session (excluding staff-only operational alerts)."""
    token = session_token or x_restaurant_session
    if not token:
        raise HTTPException(status_code=401, detail="Session token required")

    session = await PublicCustomerQRService.get_session_by_token(db, token)

    query = (
        select(Notification)
        .where(
            Notification.qr_session_id == session.id,
            Notification.type != NotificationType.BILL_REQUESTED.value,
            Notification.type != NotificationType.NEW_ORDER.value,
        )
        .order_by(Notification.created_at.desc())
    )
    res = await db.execute(query)
    items = list(res.scalars().all())

    unread = sum(1 for n in items if not n.is_read)

    return {
        "total": len(items),
        "unread_count": unread,
        "items": items,
    }


@public_notification_router.patch("/{notification_id}/read")
async def mark_public_notification_read(
    notification_id: int,
    db: SessionDep,
    x_restaurant_session: Optional[str] = Header(None, alias="X-Restaurant-Session"),
    session_token: Optional[str] = Query(None),
):
    """Marks a notification as read for the active QR session."""
    token = session_token or x_restaurant_session
    if not token:
        raise HTTPException(status_code=401, detail="Session token required")

    session = await PublicCustomerQRService.get_session_by_token(db, token)

    notif = await db.get(Notification, notification_id)
    if not notif or notif.qr_session_id != session.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    await db.commit()

    return {"success": True, "message": "Notification marked as read"}


# =============================================================================
# AUTHENTICATED NOTIFICATION ROUTER (Staff / Admin / Client)
# =============================================================================

notification_router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


async def get_effective_tenant_context(
    db: AsyncSession,
    current: dict,
    requested_client_id: Optional[int] = None,
    requested_branch_id: Optional[int] = None,
) -> tuple[Optional[int], Optional[int]]:
    """
    Authoritatively determines client_id and branch_id for the logged-in user.
    Never trusts frontend fallbacks like client_id=1.
    Strictly validates cross-tenant / cross-branch permissions.
    """
    role = current.get("role")
    user = current.get("user")

    if not user or not role:
        raise HTTPException(status_code=401, detail="Authentication required")

    if role == UserRole.STAFF:
        effective_client_id = getattr(user, "client_id", None)
        effective_branch_id = getattr(user, "branch_id", None)
        if effective_client_id is None:
            raise HTTPException(status_code=403, detail="Staff client not configured")
        if requested_client_id is not None and requested_client_id != effective_client_id:
            raise HTTPException(status_code=403, detail="Cross-tenant access forbidden for staff")
        if requested_branch_id is not None and effective_branch_id is not None and requested_branch_id != effective_branch_id:
            raise HTTPException(status_code=403, detail="Cross-branch access forbidden for staff")
        return effective_client_id, effective_branch_id

    elif role == UserRole.CLIENT:
        effective_client_id = user.id
        if requested_client_id is not None and requested_client_id != effective_client_id:
            raise HTTPException(status_code=403, detail="Cross-tenant access forbidden")
        effective_branch_id = requested_branch_id
        if effective_branch_id is not None:
            br = await db.get(Branch, effective_branch_id)
            if not br or br.client_id != effective_client_id:
                raise HTTPException(status_code=403, detail="Invalid branch for this client")
        return effective_client_id, effective_branch_id

    elif role == UserRole.PARTNER:
        if requested_client_id is None:
            raise HTTPException(status_code=400, detail="client_id parameter required for partner role")
        cl = await db.get(Client, requested_client_id)
        if not cl or cl.partner_id != user.id:
            raise HTTPException(status_code=403, detail="Access to client forbidden")
        return requested_client_id, requested_branch_id

    elif role == UserRole.SUPER_ADMIN:
        return requested_client_id, requested_branch_id

    raise HTTPException(status_code=403, detail="Access denied")


@notification_router.post("/device-token")
async def register_authenticated_device_token(
    data: DeviceTokenRegisterReq,
    db: SessionDep,
    current=Depends(access_four),
):
    """Registers or refreshes an FCM token for an authenticated staff/client/admin user."""
    role = current.get("role")
    user = current.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = None
    branch_id = None
    if role == UserRole.STAFF:
        user_id = user.id
        client_id = user.client_id
        branch_id = user.branch_id
    elif role == UserRole.CLIENT:
        user_id = None
        client_id = user.id
        branch_id = None
    else:
        client_id = getattr(user, "client_id", None)
        if not client_id and hasattr(user, "id"):
            client_id = user.id

    if not client_id:
        raise HTTPException(status_code=400, detail="Client ID could not be determined for authenticated user")

    device_token = await NotificationService.register_or_update_device_token(
        db=db,
        token=data.token,
        platform=data.platform,
        client_id=client_id,
        branch_id=branch_id,
        user_id=user_id,
        device_id=data.device_id,
    )

    return {
        "success": True,
        "message": "FCM device token registered successfully",
        "device_token_id": device_token.id,
        "is_active": device_token.is_active,
    }


@notification_router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    current=Depends(access_four),
):
    """Lists notifications for the current authenticated user/branch with pagination."""
    effective_client_id, effective_branch_id = await get_effective_tenant_context(
        db, current, requested_client_id=client_id, requested_branch_id=branch_id
    )

    query = select(Notification)
    if effective_client_id:
        query = query.where(Notification.client_id == effective_client_id)
    if effective_branch_id:
        query = query.where(
            (Notification.branch_id == effective_branch_id) | (Notification.branch_id.is_(None))
        )

    # For staff, only show notifications addressed to this user or general to branch staff
    if current.get("role") == UserRole.STAFF:
        user = current.get("user")
        query = query.where(
            (Notification.user_id == user.id) | (Notification.user_id.is_(None))
        )

    # Order by newest first
    query = query.order_by(Notification.created_at.desc())

    # Count total & unread
    total_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_res.scalar() or 0

    unread_query = query.where(Notification.is_read == False)
    unread_res = await db.execute(select(func.count()).select_from(unread_query.subquery()))
    unread = unread_res.scalar() or 0

    res = await db.execute(query.offset(skip).limit(limit))
    items = list(res.scalars().all())

    return {
        "total": total,
        "unread_count": unread,
        "items": items,
    }


@notification_router.get("/unread")
async def get_unread_count(
    db: SessionDep,
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    current=Depends(access_four),
):
    """Returns the unread notifications count for the notification bell badge."""
    effective_client_id, effective_branch_id = await get_effective_tenant_context(
        db, current, requested_client_id=client_id, requested_branch_id=branch_id
    )

    query = select(func.count(Notification.id)).where(Notification.is_read == False)
    if effective_client_id:
        query = query.where(Notification.client_id == effective_client_id)
    if effective_branch_id:
        query = query.where(
            (Notification.branch_id == effective_branch_id) | (Notification.branch_id.is_(None))
        )

    if current.get("role") == UserRole.STAFF:
        user = current.get("user")
        query = query.where(
            (Notification.user_id == user.id) | (Notification.user_id.is_(None))
        )

    res = await db.execute(query)
    count = res.scalar() or 0
    return {"unread_count": count}


@notification_router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: SessionDep,
    current=Depends(access_four),
):
    """Marks an individual notification as read with tenant isolation."""
    effective_client_id, effective_branch_id = await get_effective_tenant_context(db, current)

    notif = await db.get(Notification, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if effective_client_id and notif.client_id != effective_client_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    if effective_branch_id and notif.branch_id is not None and notif.branch_id != effective_branch_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    await db.commit()

    return {"success": True, "message": "Notification marked as read"}


@notification_router.patch("/read-all")
async def mark_all_notifications_read(
    db: SessionDep,
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    current=Depends(access_four),
):
    """Marks all unread notifications for the current user/branch as read."""
    effective_client_id, effective_branch_id = await get_effective_tenant_context(
        db, current, requested_client_id=client_id, requested_branch_id=branch_id
    )

    stmt = update(Notification).where(Notification.is_read == False)
    if effective_client_id:
        stmt = stmt.where(Notification.client_id == effective_client_id)
    if effective_branch_id:
        stmt = stmt.where(
            (Notification.branch_id == effective_branch_id) | (Notification.branch_id.is_(None))
        )

    if current.get("role") == UserRole.STAFF:
        user = current.get("user")
        stmt = stmt.where(
            (Notification.user_id == user.id) | (Notification.user_id.is_(None))
        )

    stmt = stmt.values(is_read=True, read_at=datetime.now(timezone.utc))
    await db.execute(stmt)
    await db.commit()

    return {"success": True, "message": "All notifications marked as read"}


@notification_router.post("/send/offer")
async def send_offer_notification_endpoint(
    data: SendOfferNotificationReq,
    db: SessionDep,
    current=Depends(access_one),
):
    """
    Sends an offer push notification to customer devices.
    Requires manager/client/admin role.
    """
    res = await NotificationService.send_offer_campaign(
        db=db,
        offer_id=data.offer_id,
        target_type=data.target_type,
        target_id=data.target_id,
        custom_title=data.title,
        custom_body=data.body,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@notification_router.post("/send/announcement")
async def send_announcement_endpoint(
    data: SendAnnouncementReq,
    db: SessionDep,
    current=Depends(access_one),
):
    """Sends a general restaurant announcement. Requires manager/client role."""
    effective_client_id, effective_branch_id = await get_effective_tenant_context(
        db, current, requested_branch_id=data.branch_id
    )

    return await NotificationService.send_announcement(
        db=db,
        client_id=effective_client_id,
        branch_id=effective_branch_id,
        role=data.role if data.target_type == "role" else None,
        title=data.title,
        body=data.body,
    )
