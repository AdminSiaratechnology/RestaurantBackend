# app/accounts/notification/service.py

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.bill.model import Bill
from app.accounts.customer.model import Customer
from app.accounts.notification.model import (
    CustomerNotificationPreference,
    DeviceToken,
    Notification,
    NotificationType,
)
from app.accounts.order.model import Order
from app.accounts.staff.model import Staff, StaffRole
from app.accounts.table.model import Table
from app.accounts.table_qr.model import RestaurantSession
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Firebase Admin SDK Global Handle
_firebase_initialized = False
_firebase_messaging = None


def _is_simulation_allowed() -> bool:
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    sim_env = (os.getenv("FCM_SIMULATION_MODE") or getattr(settings, "FCM_SIMULATION_MODE", "") or "").lower()
    if sim_env == "true":
        return True
    if sim_env == "false":
        return False
    app_env = (getattr(settings, "APP_ENV", None) or os.getenv("APP_ENV", "development")).lower()
    return app_env in ("development", "test", "testing", "local")


def _init_firebase() -> Optional[Any]:
    global _firebase_initialized, _firebase_messaging
    if _firebase_initialized:
        return _firebase_messaging

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None) or os.getenv("FIREBASE_CREDENTIALS_PATH", "")
        project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or getattr(settings, "FIREBASE_PROJECT_ID", None)
        has_credentials = bool(cred_path and os.path.exists(cred_path)) or bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

        if not has_credentials:
            if _is_simulation_allowed():
                logger.info("Firebase credentials not configured - running in simulation mode.")
            else:
                logger.warning("Firebase credentials not configured in production mode.")
            _firebase_initialized = True
            return None

        if not firebase_admin._apps:
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                options = {"projectId": project_id} if project_id else None
                firebase_admin.initialize_app(cred, options=options)
                logger.info("Firebase Admin SDK initialized successfully with service account.")
            elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                options = {"projectId": project_id} if project_id else None
                firebase_admin.initialize_app(options=options)
                logger.info("Firebase Admin SDK initialized with credentials/project ID.")

        _firebase_messaging = messaging
        _firebase_initialized = True
        return _firebase_messaging
    except ImportError:
        if _is_simulation_allowed():
            logger.warning("firebase-admin package not found. Running in simulation mode.")
        else:
            logger.error("firebase-admin package not found in production.")
        _firebase_initialized = True
        return None
    except Exception as exc:
        logger.warning(f"Failed to initialize Firebase Admin SDK: {exc}.")
        _firebase_initialized = True
        return None


class NotificationService:
    """
    Centralized Notification Service for Firebase Cloud Messaging (FCM).
    Ensures safe error handling: Firebase failures NEVER rollback core RMS operations.
    """

    @classmethod
    async def register_or_update_device_token(
        cls,
        db: AsyncSession,
        token: str,
        platform: str = "web",
        client_id: int = 1,
        branch_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None,
        qr_session_id: Optional[int] = None,
        device_id: Optional[str] = None,
    ) -> DeviceToken:
        """
        Registers or updates an FCM device token.
        Supports multiple devices per customer, and updates existing tokens seamlessly.
        """
        now = datetime.now(timezone.utc)

        # Check if this exact token exists
        res = await db.execute(
            select(DeviceToken).where(DeviceToken.token == token)
        )
        existing = res.scalar_one_or_none()

        if existing:
            existing.client_id = client_id
            if branch_id is not None:
                existing.branch_id = branch_id
            if customer_id is not None:
                existing.customer_id = customer_id
            if user_id is not None:
                existing.user_id = user_id
            if qr_session_id is not None:
                existing.qr_session_id = qr_session_id
            if device_id is not None:
                existing.device_id = device_id
            existing.platform = platform
            existing.is_active = True
            existing.notifications_enabled = True
            existing.last_used_at = now
            existing.updated_at = now
            await db.commit()
            await db.refresh(existing)
            return existing

        # If device_id is provided and already has an old active token for this session, deactivate it
        if device_id and qr_session_id:
            await db.execute(
                update(DeviceToken)
                .where(
                    DeviceToken.device_id == device_id,
                    DeviceToken.qr_session_id == qr_session_id,
                    DeviceToken.token != token,
                )
                .values(is_active=False)
            )

        new_device_token = DeviceToken(
            token=token,
            platform=platform,
            device_id=device_id,
            client_id=client_id,
            branch_id=branch_id,
            customer_id=customer_id,
            user_id=user_id,
            qr_session_id=qr_session_id,
            is_active=True,
            notifications_enabled=True,
            last_used_at=now,
        )
        db.add(new_device_token)
        await db.commit()
        await db.refresh(new_device_token)
        return new_device_token

    @classmethod
    async def deactivate_invalid_token(cls, db: AsyncSession, token: str) -> None:
        """Deactivates a permanently unregistered or invalid FCM token."""
        try:
            await db.execute(
                update(DeviceToken)
                .where(DeviceToken.token == token)
                .values(is_active=False, notifications_enabled=False)
            )
            await db.commit()
            logger.info(f"Deactivated invalid FCM token: {token[:12]}...")
        except Exception as e:
            logger.error(f"Error deactivating invalid token: {e}")

    @classmethod
    async def send_to_tokens(
        cls,
        db: AsyncSession,
        tokens: list[str],
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        notification_type: str = NotificationType.ANNOUNCEMENT.value,
        client_id: int = 1,
        branch_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None,
        qr_session_id: Optional[int] = None,
        order_id: Optional[int] = None,
        bill_id: Optional[int] = None,
        offer_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Sends push notification to a list of tokens via FCM.
        Persists a record in the notifications table as the authoritative source of truth.
        Catches all errors so business operations are never disrupted.
        """
        # Prepare JSON string data map for FCM payload
        data_payload = {}
        if data:
            for k, v in data.items():
                data_payload[k] = str(v) if v is not None else ""
        data_payload["type"] = notification_type
        if order_id:
            data_payload["order_id"] = str(order_id)
        if bill_id:
            data_payload["bill_id"] = str(bill_id)
        if offer_id:
            data_payload["offer_id"] = str(offer_id)

        if "target_link" not in data_payload:
            resolved_link = cls._resolve_target_link(notification_type, data_payload)
            if resolved_link:
                data_payload["target_link"] = resolved_link

        # 1. ALWAYS Save Notification History in PostgreSQL first (Source of Truth)
        notif = None
        try:
            notif = Notification(
                user_id=user_id,
                customer_id=customer_id,
                client_id=client_id,
                branch_id=branch_id,
                qr_session_id=qr_session_id,
                order_id=order_id,
                bill_id=bill_id,
                offer_id=offer_id,
                type=notification_type,
                title=title,
                body=body,
                data=data_payload,
                is_read=False,
            )
            db.add(notif)
            await db.commit()
            await db.refresh(notif)
        except Exception as e:
            logger.error(f"Failed to persist notification history: {e}")
            await db.rollback()

        # Deduplicate and filter tokens
        clean_tokens = [t.strip() for t in set(tokens or []) if t and t.strip()]

        if not clean_tokens:
            return {
                "success": True,
                "sent_count": 0,
                "failed_count": 0,
                "total_tokens": 0,
                "notification_id": notif.id if notif else None,
                "message": "Notification saved to database (no device tokens provided)",
            }

        # 2. Dispatch via Firebase Admin SDK
        messaging_mod = _init_firebase()
        sent_count = 0
        failed_count = 0

        if messaging_mod:
            try:
                # Multicast message
                message = messaging_mod.MulticastMessage(
                    tokens=clean_tokens,
                    notification=messaging_mod.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data_payload,
                    webpush=messaging_mod.WebpushConfig(
                        notification=messaging_mod.WebpushNotification(
                            title=title,
                            body=body,
                            icon="/favicon.ico",
                        ),
                        fcm_options=messaging_mod.WebpushFCMOptions(
                            link=cls._resolve_target_link(notification_type, data_payload)
                        ),
                    ),
                )
                response = messaging_mod.send_each_for_multicast(message)
                sent_count = response.success_count
                failed_count = response.failure_count

                # Clean up unregistered tokens
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        err = resp.exception
                        # Check for unregistered or invalid token error
                        if hasattr(err, "code") and ("registration-token-not-registered" in str(err.code) or "invalid-argument" in str(err.code)):
                            await cls.deactivate_invalid_token(db, clean_tokens[idx])
            except Exception as fcm_err:
                logger.error(f"FCM delivery error: {fcm_err}")
                if _is_simulation_allowed():
                    logger.warning("FCM error - falling back to simulated dispatch in dev/test.")
                    sent_count = len(clean_tokens)
                    failed_count = 0
                else:
                    failed_count = len(clean_tokens)
        else:
            # Check simulation mode permission
            if _is_simulation_allowed():
                logger.info(f"[FCM SIMULATION] Sent '{title}' to {len(clean_tokens)} token(s). Body: {body}")
                sent_count = len(clean_tokens)
            else:
                logger.warning(f"FCM not configured in production mode. Push not delivered to {len(clean_tokens)} token(s).")
                failed_count = len(clean_tokens)

        return {
            "success": True,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_tokens": len(clean_tokens),
            "notification_id": notif.id if notif else None,
        }

    @staticmethod
    def _resolve_target_link(notification_type: str, data: dict[str, str]) -> str:
        """Determines target frontend URL for notification click."""
        if notification_type in {
            NotificationType.NEW_ORDER.value,
            NotificationType.ORDER_ACCEPTED.value,
            NotificationType.ORDER_PREPARING.value,
            NotificationType.ORDER_READY.value,
            NotificationType.ORDER_SERVED.value,
            NotificationType.ORDER_CANCELLED.value,
        }:
            order_id = data.get("order_id", "")
            return f"/Orders?order_id={order_id}"
        elif notification_type == NotificationType.BILL_REQUESTED.value:
            order_id = data.get("order_id", "")
            return f"/Bills?order_id={order_id}" if order_id else "/Bills"
        elif notification_type in {NotificationType.BILL_COMPLETED.value, NotificationType.PAYMENT_SUCCESS.value}:
            bill_id = data.get("bill_id", "")
            return f"/Bills?bill_id={bill_id}" if bill_id else "/Bills"
        elif notification_type == NotificationType.OFFER.value:
            offer_id = data.get("offer_id", "")
            return f"/OfferZone?offer_id={offer_id}"
        elif notification_type == NotificationType.NEW_MENU.value:
            return "/Menu"
        elif notification_type in {NotificationType.LOYALTY_UPDATE.value, NotificationType.POINTS_EARNED.value, NotificationType.RANK_UPGRADE.value}:
            return "/Customers"
        return "/"

    # =========================================================================
    # TARGETING METHODS
    # =========================================================================

    @classmethod
    async def send_to_qr_session(
        cls,
        db: AsyncSession,
        qr_session_id: int,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        notification_type: str = NotificationType.ORDER_PREPARING.value,
        order_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Sends notification to the active device tokens of a QR session."""
        session = await db.get(RestaurantSession, qr_session_id)
        if not session:
            return {"success": False, "message": "QR session not found"}

        res = await db.execute(
            select(DeviceToken.token).where(
                DeviceToken.qr_session_id == qr_session_id,
                DeviceToken.is_active == True,
                DeviceToken.notifications_enabled == True,
            )
        )
        tokens = list(res.scalars().all())

        return await cls.send_to_tokens(
            db=db,
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            notification_type=notification_type,
            client_id=session.client_id,
            branch_id=session.branch_id,
            customer_id=session.customer_id,
            qr_session_id=qr_session_id,
            order_id=order_id,
        )

    @classmethod
    async def send_to_customer(
        cls,
        db: AsyncSession,
        customer_id: int,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        notification_type: str = NotificationType.OFFER.value,
        category: Optional[str] = None,
        order_id: Optional[int] = None,
        bill_id: Optional[int] = None,
        offer_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Sends notification to a registered customer.
        Honors CustomerNotificationPreference before dispatching marketing/engagement notifications.
        """
        customer = await db.get(Customer, customer_id)
        if not customer:
            return {"success": False, "message": "Customer not found"}

        # Check preferences if category specified
        if category:
            pref_res = await db.execute(
                select(CustomerNotificationPreference).where(
                    CustomerNotificationPreference.customer_id == customer_id
                )
            )
            pref = pref_res.scalar_one_or_none()
            if pref and getattr(pref, category, True) is False:
                logger.info(f"Customer {customer_id} opted out of {category} notifications.")
                return {"success": True, "sent_count": 0, "message": f"Customer opted out of {category}"}

        res = await db.execute(
            select(DeviceToken.token).where(
                DeviceToken.customer_id == customer_id,
                DeviceToken.is_active == True,
                DeviceToken.notifications_enabled == True,
            )
        )
        tokens = list(res.scalars().all())

        return await cls.send_to_tokens(
            db=db,
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            notification_type=notification_type,
            client_id=customer.client_id,
            branch_id=customer.branch_id,
            customer_id=customer_id,
            order_id=order_id,
            bill_id=bill_id,
            offer_id=offer_id,
        )

    @classmethod
    async def send_to_role(
        cls,
        db: AsyncSession,
        client_id: int,
        branch_id: Optional[int],
        role: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        notification_type: str = NotificationType.NEW_ORDER.value,
        order_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Sends notifications to all active staff devices of a specific role in a branch."""
        # Find staff matching branch and role
        query = select(Staff.id).where(Staff.client_id == client_id)
        if branch_id:
            query = query.where(Staff.branch_id == branch_id)
        if role:
            role_val = role.value if hasattr(role, "value") else str(role)
            try:
                role_enum = StaffRole(role_val)
            except Exception:
                role_enum = role
            query = query.where((Staff.role == role) | (Staff.role == role_val) | (Staff.role == role_enum))

        staff_ids_res = await db.execute(query)
        staff_ids = list(staff_ids_res.scalars().all())

        if not staff_ids:
            return {"success": True, "sent_count": 0, "message": f"No staff found for role {role}"}

        tokens_res = await db.execute(
            select(DeviceToken.token).where(
                DeviceToken.user_id.in_(staff_ids),
                DeviceToken.is_active == True,
                DeviceToken.notifications_enabled == True,
            )
        )
        tokens = list(tokens_res.scalars().all())

        return await cls.send_to_tokens(
            db=db,
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            notification_type=notification_type,
            client_id=client_id,
            branch_id=branch_id,
            order_id=order_id,
        )

    # =========================================================================
    # DOMAIN BUSINESS EVENT DISPATCHERS
    # =========================================================================

    @classmethod
    async def send_new_order_to_kitchen(cls, db: AsyncSession, order: Order) -> dict[str, Any]:
        """Triggered after order creation transaction commit. Alerts kitchen/chefs."""
        table_name = "Online"
        if order.table_id:
            table = await db.get(Table, order.table_id)
            if table:
                table_name = f"Table {table.name}"

        source_val = order.source.value if hasattr(order.source, "value") else str(order.source or "pos")

        title = f"New Order #{order.id}"
        body = f"New {source_val.upper()} order received from {table_name}"
        data = {
            "type": NotificationType.NEW_ORDER.value,
            "order_id": str(order.id),
            "branch_id": str(order.branch_id),
            "table_id": str(order.table_id or ""),
            "source": source_val,
        }

        # Send to kitchen / chef staff
        res = await cls.send_to_role(
            db=db,
            client_id=order.client_id,
            branch_id=order.branch_id,
            role=StaffRole.chef.value,
            title=title,
            body=body,
            data=data,
            notification_type=NotificationType.NEW_ORDER.value,
            order_id=order.id,
        )

        # Also alert active QR session device if applicable
        if order.restaurant_session_id:
            await cls.send_to_qr_session(
                db=db,
                qr_session_id=order.restaurant_session_id,
                title="Order Received",
                body=f"Your order #{order.id} has been received by the kitchen.",
                data=data,
                notification_type=NotificationType.NEW_ORDER.value,
                order_id=order.id,
            )

        return res

    @classmethod
    async def send_order_status_update(
        cls,
        db: AsyncSession,
        order: Order,
        old_status: str,
        new_status: str,
    ) -> dict[str, Any]:
        """Dispatches structured live updates to customer QR session when status changes."""
        old_s = (old_status or "").lower().strip()
        new_s = (new_status or "").lower().strip()

        if old_s == new_s:
            # Idempotency check: prevent duplicate notifications for identical status
            return {"success": True, "sent_count": 0, "message": "Status unchanged"}

        status_messages = {
            "accepted": ("Order accepted", f"Your order #{order.id} has been accepted.", NotificationType.ORDER_ACCEPTED.value),
            "preparing": ("Order is being prepared", f"Your order #{order.id} is now being prepared.", NotificationType.ORDER_PREPARING.value),
            "ready": ("Order is ready", f"Your order #{order.id} is ready.", NotificationType.ORDER_READY.value),
            "served": ("Order served", f"Your order #{order.id} has been served.", NotificationType.ORDER_SERVED.value),
            "rejected": ("Order rejected", f"Your order #{order.id} was rejected.", NotificationType.ORDER_REJECTED.value),
            "cancelled": ("Order cancelled", f"Your order #{order.id} has been cancelled.", NotificationType.ORDER_CANCELLED.value),
        }

        if new_s not in status_messages:
            return {"success": True, "sent_count": 0, "message": f"No notification configured for status '{new_s}'"}

        title, body, notif_type = status_messages[new_s]

        # Idempotency check 2: DB-level check to prevent duplicate notifications for identical order & status type
        existing = await db.execute(
            select(Notification.id).where(
                Notification.order_id == order.id,
                Notification.type == notif_type,
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(f"Order #{order.id} already has a notification for {notif_type}. Skipping duplicate.")
            return {"success": True, "sent_count": 0, "message": f"Notification '{notif_type}' already exists for order #{order.id}"}

        source_val = order.source.value if hasattr(order.source, "value") else str(order.source or "qr")

        data = {
            "type": notif_type,
            "order_id": str(order.id),
            "status": new_s,
            "table_id": str(order.table_id or ""),
            "qr_session_id": str(order.restaurant_session_id or ""),
            "branch_id": str(order.branch_id),
            "client_id": str(order.client_id),
            "source": source_val,
        }

        result = {"success": True, "sent_count": 0}

        # Send to QR session device
        if order.restaurant_session_id:
            result = await cls.send_to_qr_session(
                db=db,
                qr_session_id=order.restaurant_session_id,
                title=title,
                body=body,
                data=data,
                notification_type=notif_type,
                order_id=order.id,
            )
        elif order.customer_id:
            result = await cls.send_to_customer(
                db=db,
                customer_id=order.customer_id,
                title=title,
                body=body,
                data=data,
                notification_type=notif_type,
                category="order_updates",
                order_id=order.id,
            )

        # When an order becomes ready in kitchen, also notify branch waitstaff/managers
        if new_s == "ready":
            try:
                table_str = f"Table {order.table_id}" if order.table_id else "Order"
                if order.table_id:
                    tbl = await db.get(Table, order.table_id)
                    if tbl:
                        table_str = f"Table {tbl.name}"
                waiter_res = await cls.send_to_role(
                    db=db,
                    client_id=order.client_id,
                    branch_id=order.branch_id,
                    role=StaffRole.waiter,
                    title="Order ready",
                    body=f"Order #{order.id} is ready for {table_str}.",
                    data=data,
                    notification_type=NotificationType.ORDER_READY.value,
                    order_id=order.id,
                )
                if waiter_res and waiter_res.get("sent_count"):
                    result["sent_count"] = result.get("sent_count", 0) + waiter_res["sent_count"]
            except Exception as e:
                logger.warning(f"Could not notify waiter of ready order: {e}")

        return result

    @classmethod
    async def send_payment_success(
        cls,
        db: AsyncSession,
        order: Order,
        bill: Bill,
    ) -> dict[str, Any]:
        """Dispatched after payment verification transaction succeeds."""
        title = "Payment successful"
        body = "Your payment was received"
        data = {
            "type": NotificationType.PAYMENT_SUCCESS.value,
            "order_id": str(order.id),
            "bill_id": str(bill.id),
            "branch_id": str(order.branch_id),
            "client_id": str(order.client_id),
            "source": "qr",
        }

        if order.restaurant_session_id:
            return await cls.send_to_qr_session(
                db=db,
                qr_session_id=order.restaurant_session_id,
                title=title,
                body=body,
                data=data,
                notification_type=NotificationType.PAYMENT_SUCCESS.value,
                order_id=order.id,
            )
        elif order.customer_id:
            return await cls.send_to_customer(
                db=db,
                customer_id=order.customer_id,
                title=title,
                body=body,
                data=data,
                notification_type=NotificationType.PAYMENT_SUCCESS.value,
                category="payment_updates",
                order_id=order.id,
                bill_id=bill.id,
            )
        return {"success": True, "sent_count": 0}

    @classmethod
    async def send_bill_completed(
        cls,
        db: AsyncSession,
        bill: Bill,
    ) -> dict[str, Any]:
        """Dispatched when bill status changes to complete."""
        title = "Bill completed"
        body = f"Your bill for Order #{bill.order_id} has been completed."
        data = {
            "type": NotificationType.BILL_COMPLETED.value,
            "bill_id": str(bill.id),
            "order_id": str(bill.order_id),
            "branch_id": str(bill.branch_id),
            "client_id": str(bill.client_id),
            "source": "qr",
        }

        order = await db.get(Order, bill.order_id)
        if order and order.restaurant_session_id:
            return await cls.send_to_qr_session(
                db=db,
                qr_session_id=order.restaurant_session_id,
                title=title,
                body=body,
                data=data,
                notification_type=NotificationType.BILL_COMPLETED.value,
                order_id=order.id,
            )
        elif bill.customer_id:
            return await cls.send_to_customer(
                db=db,
                customer_id=bill.customer_id,
                title=title,
                body=body,
                data=data,
                notification_type=NotificationType.BILL_COMPLETED.value,
                category="payment_updates",
                order_id=bill.order_id,
                bill_id=bill.id,
            )
        return {"success": True, "sent_count": 0}

    @classmethod
    async def send_bill_requested(
        cls,
        db: AsyncSession,
        session: RestaurantSession,
        table: Optional[Table] = None,
        order: Optional[Order] = None,
    ) -> dict[str, Any]:
        """
        Triggered when a QR customer presses 'Call for Bill'.
        Creates a BILL_REQUESTED notification in PostgreSQL for the MAIN RMS application.
        Dispatches FCM push to branch staff devices.
        Never dispatches to QR customers.
        """
        table_name = "Table"
        table_id = session.table_id
        if table:
            table_name = f"Table {table.name}"
        elif table_id:
            tbl = await db.get(Table, table_id)
            if tbl:
                table_name = f"Table {tbl.name}"
            else:
                table_name = f"Table {table_id}"

        title = "Bill requested"
        body = f"{table_name} has requested the bill"
        data = {
            "type": NotificationType.BILL_REQUESTED.value,
            "table_id": str(table_id or ""),
            "table_name": table_name,
            "qr_session_id": str(session.id),
            "order_id": str(order.id) if order else "",
            "branch_id": str(session.branch_id),
            "client_id": str(session.client_id),
        }

        # Query staff tokens in this branch (managers, waiters, cashiers)
        staff_query = select(Staff.id).where(
            Staff.client_id == session.client_id,
        )
        if session.branch_id:
            staff_query = staff_query.where(Staff.branch_id == session.branch_id)

        staff_res = await db.execute(staff_query)
        staff_ids = list(staff_res.scalars().all())

        tokens = []
        if staff_ids:
            tok_res = await db.execute(
                select(DeviceToken.token).where(
                    DeviceToken.user_id.in_(staff_ids),
                    DeviceToken.is_active == True,
                    DeviceToken.notifications_enabled == True,
                )
            )
            tokens = list(set(tok_res.scalars().all()))

        return await cls.send_to_tokens(
            db=db,
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            notification_type=NotificationType.BILL_REQUESTED.value,
            client_id=session.client_id,
            branch_id=session.branch_id,
            qr_session_id=session.id,
            order_id=order.id if order else None,
            user_id=None,
        )

    @classmethod
    async def send_announcement(
        cls,
        db: AsyncSession,
        client_id: int,
        branch_id: Optional[int] = None,
        role: Optional[str] = None,
        title: str = "",
        body: str = "",
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Dedicated method for sending restaurant announcements."""
        payload = data or {}
        payload["type"] = NotificationType.ANNOUNCEMENT.value

        if role:
            return await cls.send_to_role(
                db=db,
                client_id=client_id,
                branch_id=branch_id,
                role=role,
                title=title,
                body=body,
                data=payload,
                notification_type=NotificationType.ANNOUNCEMENT.value,
            )

        # Broadcast to all staff devices in the branch / client
        query = select(DeviceToken.token).where(
            DeviceToken.client_id == client_id,
            DeviceToken.is_active == True,
            DeviceToken.notifications_enabled == True,
        )
        if branch_id:
            query = query.where(DeviceToken.branch_id == branch_id)

        tokens_res = await db.execute(query)
        tokens = list(set(tokens_res.scalars().all()))

        return await cls.send_to_tokens(
            db=db,
            tokens=tokens,
            title=title,
            body=body,
            data=payload,
            notification_type=NotificationType.ANNOUNCEMENT.value,
            client_id=client_id,
            branch_id=branch_id,
        )

    @classmethod
    async def send_offer_campaign(
        cls,
        db: AsyncSession,
        offer_id: int,
        target_type: str = "branch",
        target_id: Optional[int] = None,
        custom_title: Optional[str] = None,
        custom_body: Optional[str] = None,
    ) -> dict[str, Any]:
        """Broadcasts an offer to eligible customer tokens while enforcing branch/client isolation."""
        from app.accounts.offer.model import Offer

        offer = await db.get(Offer, offer_id)
        if not offer or not offer.is_active:
            return {"success": False, "message": "Offer not found or inactive"}

        title = custom_title or f"{offer.offer_name} 🎉"
        body = custom_body or (offer.description or "Check out our special limited-time offer!")
        data = {
            "type": NotificationType.OFFER.value,
            "offer_id": str(offer.id),
            "branch_id": str(offer.branch_id),
        }

        # Query eligible customer tokens respecting branch isolation and preferences
        query = (
            select(DeviceToken.token)
            .where(
                DeviceToken.is_active == True,
                DeviceToken.notifications_enabled == True,
            )
        )

        if target_type == "branch":
            query = query.where(DeviceToken.branch_id == (target_id or offer.branch_id))
        elif target_type == "client":
            # Find client_id for branch
            from app.accounts.branch.model import Branch
            branch = await db.get(Branch, offer.branch_id)
            client_id = branch.client_id if branch else target_id
            if client_id:
                query = query.where(DeviceToken.client_id == client_id)
        elif target_type == "customer" and target_id:
            return await cls.send_to_customer(
                db=db,
                customer_id=target_id,
                title=title,
                body=body,
                data=data,
                notification_type=NotificationType.OFFER.value,
                category="offers",
                offer_id=offer.id,
            )

        tokens_res = await db.execute(query)
        tokens = list(set(tokens_res.scalars().all()))

        return await cls.send_to_tokens(
            db=db,
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            notification_type=NotificationType.OFFER.value,
            branch_id=offer.branch_id,
            offer_id=offer.id,
        )

    @classmethod
    async def send_loyalty_update(
        cls,
        db: AsyncSession,
        customer_id: int,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        event_type: str = NotificationType.LOYALTY_UPDATE.value,
    ) -> dict[str, Any]:
        """Dispatches loyalty/points/wallet updates to a customer."""
        payload = data or {}
        payload["type"] = event_type
        return await cls.send_to_customer(
            db=db,
            customer_id=customer_id,
            title=title,
            body=body,
            data=payload,
            notification_type=event_type,
            category="loyalty",
        )

    @classmethod
    async def get_user_notifications(
        cls,
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Notification]:
        """Lists notifications with tenant and branch isolation."""
        query = select(Notification)
        if client_id:
            query = query.where(Notification.client_id == client_id)
        if branch_id:
            query = query.where(
                (Notification.branch_id == branch_id) | (Notification.branch_id.is_(None))
            )
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        return list(res.scalars().all())

    @classmethod
    async def get_unread_count(
        cls,
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """Returns unread notifications count for bell badge."""
        query = select(func.count(Notification.id)).where(Notification.is_read == False)
        if client_id:
            query = query.where(Notification.client_id == client_id)
        if branch_id:
            query = query.where(
                (Notification.branch_id == branch_id) | (Notification.branch_id.is_(None))
            )
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        res = await db.execute(query)
        return res.scalar() or 0

    @classmethod
    async def mark_as_read(
        cls,
        db: AsyncSession,
        notification_id: int,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None,
    ) -> bool:
        """Marks a notification as read."""
        notif = await db.get(Notification, notification_id)
        if not notif:
            return False
        if client_id and notif.client_id != client_id:
            return False
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    @classmethod
    async def mark_all_as_read(
        cls,
        db: AsyncSession,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
    ) -> int:
        """Marks all notifications as read for client / branch."""
        stmt = update(Notification).where(Notification.is_read == False)
        if client_id:
            stmt = stmt.where(Notification.client_id == client_id)
        if branch_id:
            stmt = stmt.where(
                (Notification.branch_id == branch_id) | (Notification.branch_id.is_(None))
            )
        if user_id:
            stmt = stmt.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        stmt = stmt.values(is_read=True, read_at=datetime.now(timezone.utc))
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0
