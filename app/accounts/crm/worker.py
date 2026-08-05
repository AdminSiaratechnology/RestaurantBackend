"""
app/accounts/crm/worker.py

CLI entrypoint to launch the CRM Background Processing Worker process.
Usage:
    python -m app.accounts.crm.worker
"""

import asyncio
import signal
import sys
from pathlib import Path

# Ensure root project directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.redis import check_redis_health, close_redis_connection
from app.accounts.crm.events.consumer import CRMEventConsumer
from app.accounts.crm.utils.logger import crm_logger


async def main():
    crm_logger.info("==================================================")
    crm_logger.info("Starting Enterprise CRM Background Worker Process")
    crm_logger.info("==================================================")

    # Verify Redis Connection
    is_healthy = await check_redis_health()
    if not is_healthy:
        crm_logger.critical("Redis is unreachable. Worker shutting down.")
        sys.exit(1)

    consumer = CRMEventConsumer()

    # Graceful Shutdown Handlers
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        crm_logger.info("Received termination signal. Shutting down worker...")
        consumer.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Signal handlers not implemented on Windows loop
            pass

    try:
        await consumer.start()
    except Exception as e:
        crm_logger.critical(f"Worker crashed: {e}", exc_info=True)
    finally:
        crm_logger.info("Closing Redis connection pool...")
        await close_redis_connection()
        crm_logger.info("CRM Worker process terminated cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        crm_logger.info("Worker interrupted by user. Exiting.")
