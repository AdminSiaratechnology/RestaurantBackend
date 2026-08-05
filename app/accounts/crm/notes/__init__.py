"""
CRM Notes Module.
"""

from app.accounts.crm.notes.model import CustomerNote
from app.accounts.crm.notes.router import router

__all__ = [
    "CustomerNote",
    "router",
]
