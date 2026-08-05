"""
app/accounts/crm/utils/logger.py

Structured Logging utility for CRM Background Processing.
"""

import logging
import sys

def get_crm_logger(name: str = "crm") -> logging.Logger:
    """
    Returns a structured, formatted logger for CRM processing.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [CRM] %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

crm_logger = get_crm_logger("worker")
