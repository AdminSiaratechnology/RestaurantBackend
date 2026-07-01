"""
app/core/cache.py

Redis Cache helper using Cache-Aside pattern.
All operations are async and fail gracefully — Redis errors
are logged and never propagate to the API client.
"""

import json
import logging
from typing import Any, Optional

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class Cache:
    """Static async cache helper wrapping redis_client with JSON serialization."""

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """
        Retrieve a cached value by key.

        Returns the deserialized value on cache hit, or None on miss / error.
        Logs CACHE HIT or CACHE MISS for observability.
        """
        try:
            data = await redis_client.get(key)
            if data:
                logger.debug(f"CACHE HIT  | key={key}")
                return json.loads(data)
            logger.debug(f"CACHE MISS | key={key}")
            return None
        except Exception as e:
            logger.error(f"Redis GET error | key={key} | error={e}")
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
        try:
            await redis_client.set(
                key,
                json.dumps(value, default=str),
                ex=expire,
            )
            logger.debug(f"CACHE SET  | key={key} | ttl={expire}s")
        except Exception as e:
            logger.error(f"Redis SET error | key={key} | error={e}")

    @staticmethod
    async def delete(key: str) -> None:
        """
        Delete a single key from Redis.

        Args:
            key: Redis key to remove.
        """
        try:
            await redis_client.delete(key)
            logger.debug(f"CACHE DELETE | key={key}")
        except Exception as e:
            logger.error(f"Redis DELETE error | key={key} | error={e}")

    @staticmethod
    async def delete_pattern(pattern: str) -> None:
        """
        Delete all keys matching a glob pattern (e.g. 'products:branch:*').

        Args:
            pattern: Redis glob pattern.
        """
        try:
            keys = await redis_client.keys(pattern)
            if keys:
                await redis_client.delete(*keys)
                logger.debug(f"CACHE DELETE_PATTERN | pattern={pattern} | deleted={len(keys)} keys")
            else:
                logger.debug(f"CACHE DELETE_PATTERN | pattern={pattern} | no keys found")
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN error | pattern={pattern} | error={e}")

    @staticmethod
    async def exists(key: str) -> bool:
        """
        Check whether a key exists in Redis.

        Args:
            key: Redis key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        try:
            return await redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error | key={key} | error={e}")
            return False

    @staticmethod
    async def expire(key: str, seconds: int) -> None:
        """
        Update (or set) the TTL of an existing key.

        Args:
            key:     Redis key.
            seconds: New TTL in seconds.
        """
        try:
            await redis_client.expire(key, seconds)
            logger.debug(f"CACHE EXPIRE | key={key} | ttl={seconds}s")
        except Exception as e:
            logger.error(f"Redis EXPIRE error | key={key} | error={e}")