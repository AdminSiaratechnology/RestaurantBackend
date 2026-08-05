"""
app/accounts/crm/events/publisher.py

Async Redis Event Publisher for CRM operations.
Publishes 'bill_completed' events immediately after database transaction commit.
Ensures zero latency impact on API client responses.
"""

import json
from datetime import datetime
from typing import Dict, Any

from app.core.redis import redis_client
from app.accounts.crm.config import crm_config
from app.accounts.crm.events.schema import BillCompletedEvent
from app.accounts.crm.utils.logger import crm_logger


class CRMEventPublisher:
    """
    Event Publisher using Redis Streams (XADD) for durable, decoupled event distribution.
    """

    def __init__(self, stream_key: str = crm_config.REDIS_STREAM_KEY):
        self.stream_key = stream_key

    async def publish_bill_completed(
        self,
        bill_id: int,
        order_id: int,
        customer_id: int,
        client_id: int,
        branch_id: int
    ) -> bool:
        """
        Publishes 'bill_completed' event to Redis Stream.

        Payload format:
        {
            "event": "bill_completed",
            "bill_id": 125,
            "order_id": 98,
            "customer_id": 9,
            "client_id": 1,
            "branch_id": 1,
            "timestamp": "2026-08-03T16:26:23"
        }

        Returns:
            True if successfully added to Redis, False otherwise.
        """
        event_model = BillCompletedEvent(
            event="bill_completed",
            bill_id=bill_id,
            order_id=order_id,
            customer_id=customer_id,
            client_id=client_id,
            branch_id=branch_id,
            timestamp=datetime.utcnow().isoformat()
        )

        event_payload: Dict[str, Any] = {
            "payload": json.dumps(event_model.model_dump())
        }

        try:
            # XADD adds event to Redis Stream in <2ms
            message_id = await redis_client.xadd(self.stream_key, event_payload)
            crm_logger.info(
                f"[EventPublisher] Published 'bill_completed' for Bill #{bill_id} -> Stream ID: {message_id}"
            )
            return True
        except Exception as e:
            crm_logger.error(
                f"[EventPublisher] Failed to publish 'bill_completed' for Bill #{bill_id}: {e}"
            )
            # Never raise — API response must return successfully regardless of Redis availability
            return False


# Shared instance for DI across FastAPI routes
crm_event_publisher = CRMEventPublisher()
