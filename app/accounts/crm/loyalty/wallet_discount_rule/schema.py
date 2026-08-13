from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


# =========================================================
# CREATE
# =========================================================

class WalletDiscountRuleCreate(BaseModel):

    max_wallet_discount_percent: float = Field(
        ...,
        ge=0,
        le=100,
        description=(
            "Maximum percentage of bill amount "
            "that can be paid using wallet."
        ),
    )

    is_active: bool = True


# =========================================================
# UPDATE
# =========================================================

class WalletDiscountRuleUpdate(BaseModel):

    max_wallet_discount_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    is_active: Optional[bool] = None


# =========================================================
# RESPONSE
# =========================================================

class WalletDiscountRuleResponse(BaseModel):

    id: int

    client_id: int

    branch_id: int

    max_wallet_discount_percent: float

    is_active: bool

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# CALCULATE WALLET PAYMENT
# =========================================================

class WalletPaymentCalculationResponse(BaseModel):

    bill_amount: float

    wallet_balance: float

    discount_percent: float

    maximum_wallet_amount: float

    applicable_wallet_amount: float

    customer_payable_amount: float