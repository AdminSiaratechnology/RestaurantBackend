"""
app/accounts/crm/utils/retry.py

Exponential backoff retry mechanism for CRM handlers and event consumer steps.
"""

import asyncio
import functools
from typing import Callable, Any, Type, Tuple
from app.accounts.crm.config import crm_config
from app.accounts.crm.utils.logger import crm_logger


async def execute_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = crm_config.retry.MAX_RETRIES,
    initial_delay: float = crm_config.retry.INITIAL_BACKOFF_SECONDS,
    backoff_factor: float = crm_config.retry.BACKOFF_MULTIPLIER,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    **kwargs: Any
) -> Any:
    """
    Executes an async function with exponential backoff retry logic.

    Args:
        func: Async function to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds before first retry.
        backoff_factor: Multiplier applied to delay after each retry.
        retryable_exceptions: Tuple of exceptions to catch and retry.

    Returns:
        Result of the execution if successful.

    Raises:
        The last caught exception if all retries fail.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exception = exc
            crm_logger.warning(
                f"Execution failed (Attempt {attempt}/{max_retries}) for {func.__name__}: {exc}"
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                crm_logger.error(
                    f"Max retries ({max_retries}) reached for {func.__name__}. Error: {exc}"
                )

    raise last_exception  # type: ignore


def async_retry(
    max_retries: int = crm_config.retry.MAX_RETRIES,
    initial_delay: float = crm_config.retry.INITIAL_BACKOFF_SECONDS,
    backoff_factor: float = crm_config.retry.BACKOFF_MULTIPLIER,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for async functions to enable exponential backoff retry.
    """
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await execute_with_retry(
                func,
                *args,
                max_retries=max_retries,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    return decorator
