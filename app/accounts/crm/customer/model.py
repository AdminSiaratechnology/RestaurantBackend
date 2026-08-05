"""
Re-export Customer model from app.accounts.customer.model to prevent duplication.
"""
from app.accounts.customer.model import Customer

__all__ = ["Customer"]
