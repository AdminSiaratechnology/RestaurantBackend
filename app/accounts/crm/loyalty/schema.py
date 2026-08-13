"""
app/accounts/crm/loyalty/schema.py

Pydantic schemas for Customer Loyalty.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ============================================================
# LOYALTY ACCOUNT
# ============================================================

class LoyaltyAccountOut(BaseModel):

    id: int

    customer_id: int

    client_id: int

    total_points_earned: float

    total_points_redeemed: float

    current_points_balance: float

    converted_spend: float

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# LOYALTY TRANSACTION
# ============================================================

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

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# CURRENT SPEND CONVERSION RESPONSE
# ============================================================

class LoyaltyConversionOut(BaseModel):

    message: str

    customer_id: int

    history_id: int

    bill_id: Optional[int] = None

    current_spend: float

    previously_converted_spend: float

    eligible_spend: float

    converted_spend: float

    rank: str

    points_per_100: float

    points_earned: float

    total_points_earned: float

    total_points_redeemed: float

    current_points_balance: float


# ============================================================
# LOYALTY REDEMPTION SCHEMAS
# ============================================================

class LoyaltyRedeemIn(BaseModel):

    customer_id: int

    points: float

    bill_id: Optional[int] = None

    description: Optional[str] = None


class LoyaltyRedeemOut(BaseModel):

    message: str

    customer_id: int

    points_redeemed: float

    total_points_redeemed: float

    current_points_balance: float

    current_rank: str

    total_spend: float

    current_spend: float = 0.0