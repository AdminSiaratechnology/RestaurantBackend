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
    ForeignKey,
    Index,
)

from datetime import datetime
from app.db.base import Base


class OfferType(str, enum.Enum):
    PERCENTAGE_OFF = "Percentage off"
    FLAT_DISCOUNT = "Flat discount"
    BUY_ONE_GET_ONE = "Buy 1 get 1"
    FREE_ITEM = "Free Item"


class Offer(Base):

    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_branch_id", "branch_id"),
        Index("ix_offers_is_active", "is_active"),
        Index("ix_offers_valid_from", "valid_from"),
        Index("ix_offers_valid_to", "valid_to"),
        Index(
            "ix_offers_branch_active",
            "branch_id",
            "is_active"
        ),
        )

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

    no_used = Column(
        Integer,
        default=0,
        nullable=False
    )