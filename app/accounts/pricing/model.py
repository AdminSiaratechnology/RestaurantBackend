# =========================================================
# app/accounts/pricing/model.py
# =========================================================

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)

from sqlalchemy.orm import relationship

from app.db.base import Base


# =========================================================
# PRICING
# =========================================================

class Pricing(Base):

    __tablename__ = "pricings"


    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )


    # =====================================================
    # RELATIONS
    # =====================================================

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
    )

    item_id = Column(
        Integer,
        ForeignKey("items.id"),
        nullable=False,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
    )


    # =====================================================
    # PRICE
    # =====================================================

    price = Column(
        Float,
        nullable=False,
    )

    cost_price = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    discount = Column(
        Float,
        nullable=False,
        default=0.0,
    )


    # =====================================================
    # TAX
    #
    # tax = TOTAL TAX RATE
    #
    # India:
    # tax = 18
    # CGST = 9
    # SGST = 9
    #
    # Other country:
    # tax = 15
    # VAT = 15
    # =====================================================

    tax = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    tax_type = Column(
        String(20),
        nullable=False,
    )

    cgst_rate = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    sgst_rate = Column(
        Float,
        nullable=False,
        default=0.0,
    )


    # =====================================================
    # EXTRA
    # =====================================================

    calories = Column(
        Integer,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    item = relationship(
        "Item",
        back_populates="pricings",
    )

    client = relationship(
        "Client",
        back_populates="pricings",
    )

    branch = relationship(
        "Branch",
        back_populates="pricings",
    )

    tax_history = relationship(
        "PricingTaxHistory",
        back_populates="pricing",
        cascade="all, delete-orphan",
    )


# =========================================================
# TAX HISTORY
# =========================================================

class PricingTaxHistory(Base):

    __tablename__ = "pricing_tax_history"


    id = Column(
        Integer,
        primary_key=True,
    )

    pricing_id = Column(
        Integer,
        ForeignKey("pricings.id"),
        nullable=False,
    )

    item_id = Column(
        Integer,
        ForeignKey("items.id"),
        nullable=False,
    )

    old_tax = Column(
        Float,
        nullable=False,
    )

    new_tax = Column(
        Float,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    pricing = relationship(
        "Pricing",
        back_populates="tax_history",
    )