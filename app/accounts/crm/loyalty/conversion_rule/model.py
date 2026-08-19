"""
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
    UniqueConstraint,
)

from app.db.base import Base


class LoyaltyConversionRule(Base):

    __tablename__ = "loyalty_conversion_rules"

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "branch_id",
            name="uq_loyalty_conversion_rule_client_branch",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    points_required = Column(
        Float,
        nullable=False,
    )

    rupee_value = Column(
        Float,
        nullable=False,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
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