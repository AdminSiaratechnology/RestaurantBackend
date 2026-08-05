"""
app/accounts/crm/wallet/schema.py

Pydantic schemas for Customer Wallet.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WalletAccountOut(BaseModel):
    id: int
    customer_id: int
    client_id: int
    balance: float
    total_recharged: float
    total_spent: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WalletTransactionOut(BaseModel):
    id: int
    account_id: int
    customer_id: int
    bill_id: Optional[int] = None
    transaction_type: str
    amount: float
    balance_after: float
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
