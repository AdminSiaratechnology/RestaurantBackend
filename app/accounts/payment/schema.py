from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.accounts.payment.enum import PaymentMethod


# ============================================================
# PAYMENT ITEM
# ============================================================


class PaymentItem(BaseModel):
    payment_method: PaymentMethod

    payment_amount: float = Field(
        gt=0,
        description="Actual amount received through payment method",
    )


# ============================================================
# PAYMENT CREATE
# ============================================================


class PaymentCreate(BaseModel):

    bill_id: int

    payments: List[PaymentItem]

    notes: Optional[str] = None

    payment_reference: Optional[str] = None

    offer_id: Optional[int] = None

    # ========================================================
    # WALLET
    # ========================================================
    #
    # Wallet is NOT a payment method.
    #
    # False:
    #     Bill
    #       ↓
    #     Offer
    #       ↓
    #     Cash/Card/UPI
    #
    # True:
    #     Bill
    #       ↓
    #     Offer
    #       ↓
    #     Wallet Contribution
    #       ↓
    #     Cash/Card/UPI
    #
    # IMPORTANT:
    # Wallet is deducted ONLY during successful payment
    # when this value is True.
    #
    # ========================================================

    use_wallet: bool = False


# ============================================================
# PAYMENT ITEM OUT
# ============================================================


class PaymentItemOut(BaseModel):

    payment_method: str

    payment_amount: float


# ============================================================
# PAYMENT OUT
# ============================================================


class PaymentOut(BaseModel):

    id: int

    bill_id: int

    order_id: int

    branch_id: int

    payment_method: str

    payment_breakdown: List[PaymentItemOut]

    bill_amount: float

    receive_amount: float

    paid_amount: float

    change_amount: float

    payment_reference: Optional[str]

    notes: Optional[str]

    payment_date: datetime

    offer_id: Optional[int] = None

    offer_discount: float = 0.0

    # Actual wallet contribution used during payment.
    #
    # This MUST remain 0 when use_wallet=False.
    #
    wallet_discount: float = 0.0

    model_config = ConfigDict(
        from_attributes=True
    )