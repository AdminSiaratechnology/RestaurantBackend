"""
app/accounts/crm/loyalty/conversion_rule/model.py

Branch-wise Loyalty Point -> Rupee Conversion Rules.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class LoyaltyConversionRule(Base):

    __tablename__ = "loyalty_conversion_rules"

    # ============================================================
    # PRIMARY KEY
    # ============================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ============================================================
    # CLIENT
    # ============================================================

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ============================================================
    # BRANCH
    # ============================================================

    # One conversion rule per branch.
    #
    # Example:
    #
    # Branch A -> 10 points = ₹5
    # Branch B -> 20 points = ₹5
    #
    # ============================================================

    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    # ============================================================
    # CONVERSION RATE
    # ============================================================

    # Example:
    #
    # points_required = 10
    # rupee_value = 5
    #
    # Means:
    #
    # 10 loyalty points = ₹5
    #
    # ============================================================

    points_required = Column(
        Float,
        nullable=False,
    )

    rupee_value = Column(
        Float,
        nullable=False,
    )

    # ============================================================
    # STATUS
    # ============================================================

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # ============================================================
    # DATES
    # ============================================================

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

    # ============================================================
    # RELATIONSHIPS
    # ============================================================

    branch = relationship(
        "Branch",
    )

    client = relationship(
        "Client",
    )