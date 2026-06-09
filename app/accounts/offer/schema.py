# app/accounts/offer/schema.py

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum


class OfferType(str, Enum):
    PERCENTAGE_OFF = "Percentage off"
    FLAT_DISCOUNT = "Flat discount"
    BUY_ONE_GET_ONE = "Buy 1 get 1"
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

    @field_validator("offer_type", mode="before")
    @classmethod
    def normalize_offer_type(cls, v):

        if isinstance(v, str):

            mapping = {
                "BUY_ONE_GET_ONE": OfferType.BUY_ONE_GET_ONE,
                "Buy 1 Get 1": OfferType.BUY_ONE_GET_ONE,
                "Buy 1 get 1 free": OfferType.BUY_ONE_GET_ONE,

                "PERCENTAGE_OFF": OfferType.PERCENTAGE_OFF,
                "Percentage off": OfferType.PERCENTAGE_OFF,

                "FLAT_DISCOUNT": OfferType.FLAT_DISCOUNT,
                "Flat discount": OfferType.FLAT_DISCOUNT,

                "FREE_ITEM": OfferType.FREE_ITEM,
                "Free Item": OfferType.FREE_ITEM,
            }

            return mapping.get(v, v)

        return v

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

    @field_validator("offer_type", mode="before")
    @classmethod
    def normalize_offer_type(cls, v):

        if v is None:
            return v

        mapping = {
            "BUY_ONE_GET_ONE": OfferType.BUY_ONE_GET_ONE,
            "Buy 1 Get 1": OfferType.BUY_ONE_GET_ONE,
            "Buy 1 get 1 free": OfferType.BUY_ONE_GET_ONE,

            "PERCENTAGE_OFF": OfferType.PERCENTAGE_OFF,
            "Percentage off": OfferType.PERCENTAGE_OFF,

            "FLAT_DISCOUNT": OfferType.FLAT_DISCOUNT,
            "Flat discount": OfferType.FLAT_DISCOUNT,

            "FREE_ITEM": OfferType.FREE_ITEM,
            "Free Item": OfferType.FREE_ITEM,
        }

        return mapping.get(v, v)


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