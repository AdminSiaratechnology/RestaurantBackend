"""
CRM Tags Module.
"""

from app.accounts.crm.tags.model import CustomerTag
from app.accounts.crm.tags.router import router

__all__ = [
    "CustomerTag",
    "router",
]
