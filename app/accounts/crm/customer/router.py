"""
Re-export Customer router from app.accounts.customer.router to prevent duplication.
"""
from app.accounts.customer.router import router

__all__ = ["router"]
