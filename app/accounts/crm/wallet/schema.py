"""
app/accounts/crm/wallet/schema.py

Pydantic schemas for Customer Wallet.
"""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
)


# ============================================================
# WALLET ACCOUNT
# ============================================================


class WalletAccountOut(BaseModel):

    id: int

    customer_id: int

    client_id: int

    balance: float

    total_recharged: float

    total_spent: float

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# WALLET TRANSACTION
# ============================================================


class WalletTransactionOut(BaseModel):

    id: int

    account_id: int

    customer_id: int

    bill_id: int | None = None

    transaction_type: str

    amount: float

    balance_after: float

    remarks: str | None = None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# LOYALTY -> WALLET CONVERSION RESPONSE
# ============================================================


class LoyaltyToWalletConversionOut(BaseModel):

    customer_id: int

    points_converted: float

    rupee_amount: float

    conversion_rate_points: float

    conversion_rate_rupees: float

    loyalty_points_after: float

    wallet_balance_after: float

    message: str