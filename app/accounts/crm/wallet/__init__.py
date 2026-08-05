"""
CRM Wallet Module.
"""

from app.accounts.crm.wallet.model import CustomerWalletAccount, WalletTransaction
from app.accounts.crm.wallet.router import router

__all__ = [
    "CustomerWalletAccount",
    "WalletTransaction",
    "router",
]
