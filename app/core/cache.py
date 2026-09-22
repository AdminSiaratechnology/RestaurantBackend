"""
app/core/cache.py

Redis Cache helper using Cache-Aside pattern.
All operations are async and fail gracefully — Redis errors
are logged and never propagate to the API client.
"""

import json
import logging
import time
from typing import Any, Optional

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

# Circuit breaker constants
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 10.0
_redis_available: bool = True
_last_redis_failure: float = 0.0


def _should_skip_redis() -> bool:
    global _redis_available, _last_redis_failure
    if _redis_available:
        return False
    if time.monotonic() - _last_redis_failure < CIRCUIT_BREAKER_COOLDOWN_SECONDS:
        return True
    return False


def _record_redis_success() -> None:
    global _redis_available
    _redis_available = True


def _record_redis_failure(error: Exception) -> None:
    global _redis_available, _last_redis_failure
    _redis_available = False
    _last_redis_failure = time.monotonic()
    logger.warning(f"Redis operation failed, enabling {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s circuit breaker: {error}")


class Cache:
    """Static async cache helper wrapping redis_client with JSON serialization and circuit breaker."""

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """
        Retrieve a cached value by key.

        Returns the deserialized value on cache hit, or None on miss / error.
        Logs CACHE HIT or CACHE MISS for observability.
        """
        if _should_skip_redis():
            return None

        try:
            data = await redis_client.get(key)
            _record_redis_success()
            if data:
                logger.debug(f"CACHE HIT  | key={key}")
                return json.loads(data)
            logger.debug(f"CACHE MISS | key={key}")
            return None
        except Exception as e:
            _record_redis_failure(e)
            return None

    @staticmethod
    async def set(key: str, value: Any, expire: int = 300) -> None:
        """
        Store a value in Redis with JSON serialization and a TTL.

        Args:
            key:    Redis key.
            value:  Python object — must be JSON-serializable.
            expire: TTL in seconds (default 300).
        """
        if _should_skip_redis():
            return

        try:
            await redis_client.set(
                key,
                json.dumps(value, default=str),
                ex=expire,
            )
            _record_redis_success()
            logger.debug(f"CACHE SET  | key={key} | ttl={expire}s")
        except Exception as e:
            _record_redis_failure(e)

    @staticmethod
    async def delete(key: str) -> None:
        """
        Delete a single key from Redis.

        Args:
            key: Redis key to remove.
        """
        if _should_skip_redis():
            return

        try:
            await redis_client.delete(key)
            _record_redis_success()
            logger.debug(f"CACHE DELETE | key={key}")
        except Exception as e:
            _record_redis_failure(e)

    @staticmethod
    async def delete_pattern(pattern: str) -> None:
        """
        Delete all keys matching a glob pattern (e.g. 'products:branch:*').

        Args:
            pattern: Redis glob pattern.
        """
        if _should_skip_redis():
            return

        try:
            keys = await redis_client.keys(pattern)
            if keys:
                await redis_client.delete(*keys)
                logger.debug(f"CACHE DELETE_PATTERN | pattern={pattern} | deleted={len(keys)} keys")
            else:
                logger.debug(f"CACHE DELETE_PATTERN | pattern={pattern} | no keys found")
            _record_redis_success()
        except Exception as e:
            _record_redis_failure(e)

    @staticmethod
    async def exists(key: str) -> bool:
        """
        Check whether a key exists in Redis.

        Args:
            key: Redis key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        if _should_skip_redis():
            return False

        try:
            res = await redis_client.exists(key) > 0
            _record_redis_success()
            return res
        except Exception as e:
            _record_redis_failure(e)
            return False

    @staticmethod
    async def expire(key: str, seconds: int) -> None:
        """
        Update (or set) the TTL of an existing key.

        Args:
            key:     Redis key.
            seconds: New TTL in seconds.
        """
        if _should_skip_redis():
            return

        try:
            await redis_client.expire(key, seconds)
            _record_redis_success()
            logger.debug(f"CACHE EXPIRE | key={key} | ttl={seconds}s")
        except Exception as e:
            _record_redis_failure(e)

    @staticmethod
    async def clear_menu_cache(branch_id: int, client_id: Optional[int] = None) -> None:
        """
        Invalidate all menu and product cache keys for a specific branch.
        """
        try:
            await Cache.delete_pattern(f"products:branch:{branch_id}:*")
            await Cache.delete_pattern(f"menu:branch:{branch_id}*")
            await Cache.delete_pattern(f"menu:client:*:branch:{branch_id}*")
            if client_id:
                await Cache.delete_pattern(f"menu:client:{client_id}:branch:{branch_id}*")
            logger.debug(f"CACHE CLEAR_MENU_CACHE | branch_id={branch_id} | client_id={client_id}")
        except Exception as e:
            logger.error(f"Redis CLEAR_MENU_CACHE error | branch_id={branch_id} | error={e}")