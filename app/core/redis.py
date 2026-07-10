"""
app/core/redis.py

Async Redis client module for the Restaurant Management System.

Responsibilities:
  - Create async Redis connection using a connection pool.
  - Provide health check utility.
  - Provide graceful connection teardown.
  - Expose a test endpoint (dev only).

Redis failures are always caught and logged — they never crash the API.
"""

import logging
import redis.asyncio as redis
from fastapi import APIRouter
from decouple import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection Pool
# ---------------------------------------------------------------------------

# pool = redis.ConnectionPool(
#     host="localhost",
#     port=6379,
#     db=0,
#     decode_responses=True,
#     max_connections=100,
# )

# # Shared async Redis client — reuses the connection pool across all requests.
# redis_client: redis.Redis = redis.Redis(connection_pool=pool)

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")

pool = redis.ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=100,
)

redis_client = redis.Redis(connection_pool=pool)
# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

async def check_redis_health() -> bool:
    """
    Ping Redis to verify the connection is alive.

    Returns:
        True if Redis responds, False if unreachable.
    """
    try:
        await redis_client.ping()
        logger.info("Redis connection healthy.")
        return True
    except Exception as e:
        logger.error(f"Redis Health Check Failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Graceful Shutdown
# ---------------------------------------------------------------------------

async def close_redis_connection() -> None:
    """
    Close the Redis connection pool gracefully on application shutdown.
    """
    try:
        await redis_client.aclose()
        logger.info("Redis connection closed.")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")


# ---------------------------------------------------------------------------
# Dev / Test Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/redis-test", tags=["Health"])
async def redis_test() -> dict:
    """
    Simple endpoint to verify Redis read/write is working.
    For development and diagnostics only.
    """
    try:
        await redis_client.set("test", "Hello Memurai!")
        value = await redis_client.get("test")
        return {"status": "ok", "message": value}
    except Exception as e:
        logger.error(f"Redis test endpoint error: {e}")
        return {"status": "error", "message": str(e)}