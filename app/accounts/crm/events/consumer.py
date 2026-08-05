"""
app/accounts/crm/events/consumer.py

Redis Consumer Group worker for async CRM event processing.
Handles Stream Reading (XREADGROUP), Idempotency Guard, Retry Loop, and Dead-Letter Queue (DLQ).
"""

import asyncio
import json
from typing import Dict, Any

from app.core.redis import redis_client
from app.db.config import async_session
from app.accounts.crm.config import crm_config
from app.accounts.crm.events.dispatcher import CRMEventDispatcher
from app.accounts.crm.events.schema import BillCompletedEvent
from app.accounts.crm.utils.idempotency import IdempotencyManager
from app.accounts.crm.utils.logger import crm_logger
from app.accounts.crm.utils.retry import execute_with_retry


class CRMEventConsumer:
    """
    Asynchronous Redis Consumer Group Worker for consuming CRM events.
    """

    def __init__(self, dispatcher: CRMEventDispatcher = None):
        self.stream_key = crm_config.REDIS_STREAM_KEY
        self.group_name = crm_config.REDIS_CONSUMER_GROUP
        self.consumer_name = crm_config.REDIS_CONSUMER_NAME
        self.dlq_key = crm_config.REDIS_DLQ_KEY
        self.dispatcher = dispatcher or CRMEventDispatcher()
        self.is_running = False

    async def init_consumer_group(self) -> None:
        """
        Ensures Redis Stream and Consumer Group exist before listening.
        """
        try:
            # MKSTREAM creates stream if it doesn't exist
            await redis_client.xgroup_create(
                name=self.stream_key,
                groupname=self.group_name,
                id="0",
                mkstream=True
            )
            crm_logger.info(f"[Consumer] Created consumer group '{self.group_name}' on stream '{self.stream_key}'")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                crm_logger.info(f"[Consumer] Consumer group '{self.group_name}' already exists.")
            else:
                crm_logger.error(f"[Consumer] Error creating consumer group: {e}")

    async def push_to_dlq(self, message_id: str, raw_payload: str, error: Exception) -> None:
        """
        Routes failed messages after max retries to Dead Letter Queue (DLQ) for analysis/replay.
        """
        dlq_entry = {
            "message_id": message_id,
            "raw_payload": raw_payload,
            "error": str(error),
            "consumer": self.consumer_name,
        }
        try:
            await redis_client.lpush(self.dlq_key, json.dumps(dlq_entry))
            crm_logger.error(f"[Consumer] Pushed failed message {message_id} to DLQ '{self.dlq_key}'")
        except Exception as e:
            crm_logger.critical(f"[Consumer] Failed pushing to DLQ: {e}")

    async def process_message(self, message_id: str, message_data: Dict[str, Any]) -> None:
        """
        Processes a single message consumed from Redis Stream:
        1. Parses event payload.
        2. Idempotency Check.
        3. Dispatcher execution inside isolated DB session.
        4. Mark as processed & Acknowledge (`XACK`).
        """
        raw_payload = message_data.get("payload")
        if not raw_payload:
            crm_logger.warning(f"[Consumer] Message {message_id} has no payload. Acking.")
            await redis_client.xack(self.stream_key, self.group_name, message_id)
            return

        try:
            event_dict = json.loads(raw_payload)
            event = BillCompletedEvent(**event_dict)
        except Exception as e:
            crm_logger.error(f"[Consumer] Failed parsing payload for message {message_id}: {e}")
            await self.push_to_dlq(message_id, raw_payload, e)
            await redis_client.xack(self.stream_key, self.group_name, message_id)
            return

        # Open dedicated async database session for this event
        async with async_session() as db_session:
            try:
                # 1. Idempotency Guard Check
                already_processed = await IdempotencyManager.is_already_processed(
                    db_session=db_session,
                    event_type=event.event,
                    reference_id=str(event.bill_id)
                )

                if already_processed:
                    crm_logger.warning(
                        f"[Consumer] Event '{event.event}' for Bill #{event.bill_id} already processed. Acking."
                    )
                    await redis_client.xack(self.stream_key, self.group_name, message_id)
                    return

                # 2. Execute Dispatcher with Retry wrapper
                async def _run_dispatcher():
                    return await self.dispatcher.dispatch(event=event, db_session=db_session)

                await execute_with_retry(
                    _run_dispatcher,
                    max_retries=crm_config.retry.MAX_RETRIES,
                    initial_delay=crm_config.retry.INITIAL_BACKOFF_SECONDS,
                    backoff_factor=crm_config.retry.BACKOFF_MULTIPLIER
                )

                # 3. Mark processed in DB & Commit session
                await IdempotencyManager.mark_as_processed(
                    db_session=db_session,
                    event_type=event.event,
                    reference_id=str(event.bill_id),
                    client_id=event.client_id,
                    branch_id=event.branch_id,
                    worker_id=self.consumer_name,
                    details=f"Processed by {self.consumer_name}"
                )

                await db_session.commit()

                # 4. Acknowledge message in Redis Stream
                await redis_client.xack(self.stream_key, self.group_name, message_id)
                crm_logger.info(f"[Consumer] Successfully processed & ACKed message {message_id}")

            except Exception as exc:
                await db_session.rollback()
                crm_logger.error(f"[Consumer] Failed processing message {message_id}: {exc}")
                await self.push_to_dlq(message_id, raw_payload, exc)
                # Acknowledge to prevent endless loop blocking the stream
                await redis_client.xack(self.stream_key, self.group_name, message_id)

    async def start(self) -> None:
        """
        Starts the infinite async worker consumer loop.
        """
        await self.init_consumer_group()
        self.is_running = True
        crm_logger.info(f"[Consumer] Worker '{self.consumer_name}' started listening on '{self.stream_key}'...")

        while self.is_running:
            try:
                # Read 10 messages with 2000ms block
                streams = await redis_client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},
                    count=10,
                    block=2000
                )

                if not streams:
                    await asyncio.sleep(0.1)
                    continue

                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        await self.process_message(message_id, message_data)

            except asyncio.CancelledError:
                crm_logger.info(f"[Consumer] Worker '{self.consumer_name}' cancelled.")
                self.is_running = False
                break
            except Exception as e:
                crm_logger.error(f"[Consumer] Loop error: {e}")
                await asyncio.sleep(1.0)

    def stop(self) -> None:
        self.is_running = False
