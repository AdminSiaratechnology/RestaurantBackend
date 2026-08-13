"""
app/accounts/crm/rank_rules/model.py

Branch-wise Customer Rank Rules.

Rank is decided based on branch-wise customer spend.

Example:

Bronze: ₹0 - ₹5,000
Silver: ₹5,000 - ₹10,000
Gold:   ₹10,000+

Points:

Bronze -> 1 point per ₹100
Silver -> 2 points per ₹100
Gold   -> 3 points per ₹100
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
from sqlalchemy.orm import relationship

from app.db.base import Base


class CRMBranchRankRule(Base):

    __tablename__ = "crm_branch_rank_rules"

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "branch_id",
            name="uq_crm_branch_rank_rule_client_branch",
        ),
    )

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =====================================================
    # TENANT
    # =====================================================

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # BRANCH
    # =====================================================

    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # RANK SPEND THRESHOLDS
    # =====================================================

    bronze_min = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    bronze_max = Column(
        Float,
        nullable=False,
    )

    silver_min = Column(
        Float,
        nullable=False,
    )

    silver_max = Column(
        Float,
        nullable=False,
    )

    gold_min = Column(
        Float,
        nullable=False,
    )

    # =====================================================
    # RANK POINTS
    # =====================================================

    bronze_pts = Column(
        Float,
        nullable=False,
        default=1.0,
    )

    silver_pts = Column(
        Float,
        nullable=False,
        default=2.0,
    )

    gold_pts = Column(
        Float,
        nullable=False,
        default=3.0,
    )

    # =====================================================
    # STATUS
    # =====================================================

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    client = relationship(
        "Client",
        back_populates="crm_rank_rules",
    )

    branch = relationship(
        "Branch",
        back_populates="crm_rank_rules",
    )