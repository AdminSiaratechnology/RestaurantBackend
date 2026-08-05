"""
app/accounts/crm/loyalty/schema.py

Pydantic schemas for Customer Loyalty.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class LoyaltyAccountOut(BaseModel):
    id: int
    customer_id: int
    client_id: int
    total_points_earned: float
    total_points_redeemed: float
    current_points_balance: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoyaltyTransactionOut(BaseModel):
    id: int
    account_id: int
    customer_id: int
    bill_id: Optional[int] = None
    transaction_type: str
    points: float
    balance_after: float
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
