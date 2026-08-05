"""
app/accounts/crm/rank_rules/model.py

SQLAlchemy Model for Branch-wise Customer Rank Rules.
Configures spend-based rank classification thresholds (Bronze, Silver, Gold) per branch.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    DateTime,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class CRMBranchRankRule(Base):
    __tablename__ = "crm_branch_rank_rules"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)

    bronze_min = Column(Float, default=0.0, nullable=False)
    bronze_max = Column(Float, nullable=False)
    silver_min = Column(Float, nullable=False)
    silver_max = Column(Float, nullable=False)
    gold_min = Column(Float, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    client = relationship("Client")
    branch = relationship("Branch")
