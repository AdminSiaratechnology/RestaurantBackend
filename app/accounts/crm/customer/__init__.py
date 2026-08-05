"""
CRM Customer proxy module re-exporting from app.accounts.customer.
"""
from app.accounts.customer.model import Customer
from app.accounts.customer.router import router

__all__ = ["Customer", "router"]
