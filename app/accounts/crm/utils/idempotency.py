"""
app/accounts/crm/utils/idempotency.py

Idempotency utility manager using Redis SETNX + PostgreSQL database persistence.
Prevents duplicate event execution across distributed workers.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.redis import redis_client
from app.accounts.crm.config import crm_config
from app.accounts.crm.utils.logger import crm_logger


class IdempotencyManager:
    """
    Dual-layer idempotency guard:
    1. Redis Fast Lock (`SETNX` with TTL)
    2. PostgreSQL Transaction Record (`CRMProcessedEvent` table)
    """

    @staticmethod
    def _build_redis_key(event_type: str, reference_id: str) -> str:
        return f"crm:idempotency:{event_type}:{reference_id}"

    @classmethod
    async def is_already_processed(
        cls,
        db_session: AsyncSession,
        event_type: str,
        reference_id: str
    ) -> bool:
        """
        Checks if the event has already been processed using Redis key or DB table.
        """
        from app.accounts.crm.events.model import CRMProcessedEvent

        redis_key = cls._build_redis_key(event_type, reference_id)

        # 1. Fast path: Redis check
        try:
            exists = await redis_client.get(redis_key)
            if exists:
                crm_logger.info(f"[Idempotency] Redis hit: Event {event_type}:{reference_id} already processed.")
                return True
        except Exception as e:
            crm_logger.warning(f"[Idempotency] Redis check failed: {e}")

        # 2. Durable path: Database check
        stmt = select(CRMProcessedEvent).where(
            CRMProcessedEvent.event_type == event_type,
            CRMProcessedEvent.reference_id == str(reference_id)
        )
        result = await db_session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            crm_logger.info(f"[Idempotency] DB hit: Event {event_type}:{reference_id} already processed.")
            # Sync back to Redis cache
            try:
                await redis_client.set(redis_key, "1", ex=crm_config.IDEMPOTENCY_TTL_SECONDS)
            except Exception:
                pass
            return True

        return False

    @classmethod
    async def mark_as_processed(
        cls,
        db_session: AsyncSession,
        event_type: str,
        reference_id: str,
        client_id: int,
        branch_id: int,
        worker_id: Optional[str] = None,
        details: Optional[str] = None
    ) -> None:
        """
        Marks an event as successfully processed in both DB and Redis cache.
        """
        from app.accounts.crm.events.model import CRMProcessedEvent
        redis_key = cls._build_redis_key(event_type, reference_id)

        # Save to PostgreSQL
        processed_event = CRMProcessedEvent(
            event_type=event_type,
            reference_id=str(reference_id),
            client_id=client_id,
            branch_id=branch_id,
            worker_id=worker_id or crm_config.REDIS_CONSUMER_NAME,
            status="SUCCESS",
            details=details
        )
        db_session.add(processed_event)
        await db_session.flush()

        # Set Redis lock with TTL
        try:
            await redis_client.set(redis_key, "1", ex=crm_config.IDEMPOTENCY_TTL_SECONDS)
        except Exception as e:
            crm_logger.warning(f"[Idempotency] Failed to set Redis idempotency key: {e}")
