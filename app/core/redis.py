"""
app/core/redis.py

Async Redis client module for the Restaurant Management System.

Responsibilities:
  - Create async Redis connection using a shared connection pool.
  - Provide health check utility with structured, safe logging.
  - Provide graceful connection teardown on shutdown.
  - Expose a test endpoint (dev only).

Redis failures are caught and logged safely to prevent API disruption.
"""

import logging
from urllib.parse import urlparse
import redis.asyncio as redis
from fastapi import APIRouter
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Sanitize Redis URL for safe logging (hides passwords if present)
def get_sanitized_redis_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        db = parsed.path.lstrip("/") or "0"
        return f"redis://{hostname}:{port}/{db}"
    except Exception:
        return "redis://***"

REDIS_URL = settings.REDIS_URL
SANITIZED_REDIS_URL = get_sanitized_redis_url(REDIS_URL)

# ---------------------------------------------------------------------------
# Shared Connection Pool & Async Client
# ---------------------------------------------------------------------------

pool = redis.ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=100,
    socket_timeout=2.0,
    socket_connect_timeout=2.0,
    retry_on_timeout=False,
)

redis_client: redis.Redis = redis.Redis(connection_pool=pool)


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
        logger.info(f"Redis connection healthy ({SANITIZED_REDIS_URL}).")
        print("Redis Connected")
        return True
    except Exception as e:
        logger.error(f"Redis Health Check Failed ({SANITIZED_REDIS_URL}): {e}")
        print(f"Redis Unavailable ({type(e).__name__})")
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
        return {"status": "ok", "message": value, "redis_url": SANITIZED_REDIS_URL}
    except Exception as e:
        logger.error(f"Redis test endpoint error: {e}")
        return {"status": "error", "message": str(e), "redis_url": SANITIZED_REDIS_URL}