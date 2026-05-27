# app/accounts/offer/model.py

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Enum,
    Boolean,
    ForeignKey
)

from datetime import datetime
from app.db.base import Base


class OfferType(str, enum.Enum):
    PERCENTAGE_OFF = "Percentage off"
    FLAT_DISCOUNT = "Flat discount"
    BUY_ONE_GET_ONE = "Buy 1 get 1 free"
    FREE_ITEM = "Free Item"


class Offer(Base):

    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)

    branch_id = Column(
        Integer,
        ForeignKey("branches.id")
    )

    offer_name = Column(
        String,
        nullable=False
    )

    description = Column(String)

    offer_type = Column(
        Enum(OfferType),
        nullable=False
    )

    discount_value = Column(
        Float,
        nullable=True
    )

    min_order_amount = Column(
        Float,
        default=0
    )

    valid_from = Column(
        DateTime,
        nullable=False
    )

    valid_to = Column(
        DateTime,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )