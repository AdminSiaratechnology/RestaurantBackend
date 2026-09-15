from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.accounts.online_platforms.model import (
    OnlinePlatformConnection,
)

from app.accounts.webhooks.model import (
    WebhookEvent,
    WebhookEventStatus,
)


# =========================================================
# UBER CLIENT SECRET
# =========================================================

async def get_uber_client_secret(
    db,
    request=None,
) -> str | None:
    """
    Get Uber client secret from the active Uber platform
    connection.

    Supported model structures:

    1. connection.client_secret

    OR

    2. connection.config["client_secret"]

    OR

    3. connection.credentials["client_secret"]

    The request parameter is currently kept so the router
    interface can later be extended to identify a specific
    branch/store.
    """

    # -----------------------------------------------------
    # Get active Uber connection(s)
    # -----------------------------------------------------

    result = await db.execute(
        select(OnlinePlatformConnection)
        .where(
            OnlinePlatformConnection.platform == "uber_eats",
            OnlinePlatformConnection.status == "active",
        )
    )

    connections = result.scalars().all()

    if not connections:
        return None

    # -----------------------------------------------------
    # Find a connection containing the secret
    # -----------------------------------------------------

    for connection in connections:

        # =================================================
        # OPTION 1
        # connection.client_secret
        # =================================================

        client_secret = getattr(
            connection,
            "client_secret",
            None,
        )

        if client_secret:
            return client_secret

        # =================================================
        # OPTION 2
        # connection.config
        # =================================================

        config = getattr(
            connection,
            "config",
            None,
        )

        if isinstance(config, dict):

            client_secret = config.get(
                "client_secret"
            )

            if client_secret:
                return client_secret

        # =================================================
        # OPTION 3
        # connection.credentials
        # =================================================

        credentials = getattr(
            connection,
            "credentials",
            None,
        )

        if isinstance(credentials, dict):

            client_secret = credentials.get(
                "client_secret"
            )

            if client_secret:
                return client_secret

    return None


# =========================================================
# PROCESS UBER WEBHOOK
# =========================================================

async def process_uber_webhook(
    db,
    payload,
):

    event_id = payload.event_id

    # =====================================================
    # CHECK DUPLICATE
    # =====================================================

    result = await db.execute(
        select(WebhookEvent)
        .where(
            WebhookEvent.platform == "uber_eats",
            WebhookEvent.event_id == event_id,
        )
    )

    existing_event = result.scalar_one_or_none()

    if existing_event:

        return {
            "success": True,
            "duplicate": True,
            "event_id": event_id,
            "status": existing_event.status.value
            if hasattr(existing_event.status, "value")
            else existing_event.status,
        }

    # =====================================================
    # CREATE WEBHOOK EVENT
    # =====================================================

    external_order_id = None

    if payload.meta:

        external_order_id = (
            payload.meta.resource_id
        )

    webhook_event = WebhookEvent(
        platform="uber_eats",
        event_id=event_id,
        event_type=payload.event_type,
        external_order_id=external_order_id,
        status=WebhookEventStatus.PROCESSING,
        payload=payload.model_dump(
            mode="json"
        ),
    )

    db.add(webhook_event)

    try:

        # =================================================
        # FLUSH
        # =================================================

        await db.flush()

        # =================================================
        # EVENT ROUTING
        # =================================================

        if payload.event_type == "orders.notification":

            await process_uber_order_notification(
                db=db,
                payload=payload,
                webhook_event=webhook_event,
            )

        elif payload.event_type == "orders.cancel":

            await process_uber_order_cancel(
                db=db,
                payload=payload,
                webhook_event=webhook_event,
            )

        elif payload.event_type == "orders.failure":

            await process_uber_order_failure(
                db=db,
                payload=payload,
                webhook_event=webhook_event,
            )

        elif payload.event_type == "store.provisioned":

            await process_uber_store_provisioned(
                db=db,
                payload=payload,
                webhook_event=webhook_event,
            )

        elif payload.event_type == "store.deprovisioned":

            await process_uber_store_deprovisioned(
                db=db,
                payload=payload,
                webhook_event=webhook_event,
            )

        else:

            # Unknown event types should be recorded,
            # but should not break the webhook.

            pass

        # =================================================
        # MARK PROCESSED
        # =================================================

        webhook_event.status = (
            WebhookEventStatus.PROCESSED
        )

        webhook_event.processed_at = (
            datetime.now(timezone.utc)
        )

        webhook_event.error_message = None

        await db.commit()

        return {
            "success": True,
            "duplicate": False,
            "event_id": event_id,
            "status": "processed",
        }

    except Exception as exc:

        # =================================================
        # MARK FAILED
        # =================================================

        webhook_event.status = (
            WebhookEventStatus.FAILED
        )

        webhook_event.error_message = str(exc)

        webhook_event.processed_at = None

        await db.commit()

        # -------------------------------------------------
        # Re-raise so router can return an appropriate
        # response to Uber.
        # -------------------------------------------------

        raise


# =========================================================
# ORDERS.NOTIFICATION
# =========================================================

async def process_uber_order_notification(
    db,
    payload,
    webhook_event,
):
    """
    Handle Uber order notification.

    TODO:
        Fetch complete order from Uber using
        resource_href/resource_id and create/update
        RMS Order + OnlineOrderDetail.

    """

    external_order_id = None

    if payload.meta:

        external_order_id = (
            payload.meta.resource_id
        )

    if external_order_id:

        webhook_event.external_order_id = (
            external_order_id
        )

    # -----------------------------------------------------
    # Actual Uber order synchronization should happen here.
    # -----------------------------------------------------

    return


# =========================================================
# ORDERS.CANCEL
# =========================================================

async def process_uber_order_cancel(
    db,
    payload,
    webhook_event,
):

    external_order_id = None

    if payload.meta:

        external_order_id = (
            payload.meta.resource_id
        )

    if external_order_id:

        webhook_event.external_order_id = (
            external_order_id
        )

    # -----------------------------------------------------
    # TODO:
    #
    # Find OnlineOrderDetail using external_order_id
    # and cancel the corresponding RMS order.
    # -----------------------------------------------------

    return


# =========================================================
# ORDERS.FAILURE
# =========================================================

async def process_uber_order_failure(
    db,
    payload,
    webhook_event,
):

    external_order_id = None

    if payload.meta:

        external_order_id = (
            payload.meta.resource_id
        )

    if external_order_id:

        webhook_event.external_order_id = (
            external_order_id
        )

    # -----------------------------------------------------
    # TODO:
    #
    # Mark the corresponding online order as failed.
    # -----------------------------------------------------

    return


# =========================================================
# STORE.PROVISIONED
# =========================================================

async def process_uber_store_provisioned(
    db,
    payload,
    webhook_event,
):

    # -----------------------------------------------------
    # TODO:
    #
    # Handle Uber store provisioning.
    # -----------------------------------------------------

    return


# =========================================================
# STORE.DEPROVISIONED
# =========================================================

async def process_uber_store_deprovisioned(
    db,
    payload,
    webhook_event,
):

    # -----------------------------------------------------
    # TODO:
    #
    # Handle Uber store deprovisioning.
    # -----------------------------------------------------

    return