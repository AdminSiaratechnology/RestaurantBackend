from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.accounts.payment.enum import (
    PaymentMethod
)


class PaymentCreate(BaseModel):

    bill_id: int

    payment_method: PaymentMethod

    receive_amount: float

    notes: Optional[str] = None

    payment_reference: Optional[str] = None

    offer_id: Optional[int] = None

    offer_discount: Optional[float] = 0.0

    final_amount: Optional[float] = None


class PaymentOut(BaseModel):

    id: int

    bill_id: int

    order_id: int

    branch_id: int

    payment_method: str

    bill_amount: float

    receive_amount: float

    paid_amount: float

    change_amount: float

    payment_reference: Optional[str]

    notes: Optional[str]

    payment_date: datetime

    offer_id: Optional[int] = None

    offer_discount: Optional[float] = 0.0

    class Config:
        from_attributes = True