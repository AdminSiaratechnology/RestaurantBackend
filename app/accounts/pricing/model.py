# =========================================================
# app/accounts/pricing/model.py
# =========================================================

from sqlalchemy import (
    Column,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class Pricing(Base):
    __tablename__ = "pricings"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False
    )

    item_id = Column(
        Integer,
        ForeignKey("items.id"),
        nullable=False
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id")
    )

    # =====================================================
    # PRICING
    # =====================================================

    price = Column(Float, nullable=False)

    cost_price = Column(
        Float,
        nullable=True,
        default=0.0
    )

    # =====================================================
    # DISCOUNT
    # =====================================================

    discount = Column(
        Float,
        nullable=True,
        default=0.0
    )

    # =====================================================
    # TAX
    # =====================================================

    tax = Column(
        Float,
        nullable=True,
        default=5.0
    )

    cgst_rate = Column(
        Float,
        nullable=True,
        default=2.5
    )

    sgst_rate = Column(
        Float,
        nullable=True,
        default=2.5
    )

    # =====================================================
    # EXTRA
    # =====================================================

    calories = Column(Integer, nullable=True)

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    item = relationship(
        "Item",
        back_populates="pricings"
    )

    client = relationship(
        "Client",
        back_populates="pricings"
    )

    branch = relationship(
        "Branch",
        back_populates="pricings"
    )
    