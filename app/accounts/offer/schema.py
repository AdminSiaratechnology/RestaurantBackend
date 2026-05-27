# app/accounts/offer/schema.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class OfferType(str, Enum):
    PERCENTAGE_OFF = "Percentage off"
    FLAT_DISCOUNT = "Flat discount"
    BUY_ONE_GET_ONE = "Buy 1 get 1 free"
    FREE_ITEM = "Free Item"


# ================================
# CREATE
# ================================

class OfferCreate(BaseModel):

    branch_id: int

    offer_name: str
    description: Optional[str] = None

    offer_type: OfferType

    discount_value: Optional[float] = None

    min_order_amount: Optional[float] = 0

    valid_from: datetime
    valid_to: datetime


# ================================
# UPDATE
# ================================

class OfferUpdate(BaseModel):

    offer_name: Optional[str] = None
    description: Optional[str] = None

    offer_type: Optional[OfferType] = None

    discount_value: Optional[float] = None

    min_order_amount: Optional[float] = None

    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    is_active: Optional[bool] = None


# ================================
# RESPONSE
# ================================

class OfferResponse(BaseModel):

    id: int
    branch_id: int

    offer_name: str
    description: Optional[str]

    offer_type: OfferType

    discount_value: Optional[float]

    min_order_amount: float

    valid_from: datetime
    valid_to: datetime

    is_active: bool

    class Config:
        from_attributes = True