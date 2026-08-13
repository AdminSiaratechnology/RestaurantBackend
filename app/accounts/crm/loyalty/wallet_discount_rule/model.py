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


class WalletDiscountRule(Base):
    """
    Branch-wise wallet payment/discount rule.

    Example:

    max_wallet_discount_percent = 20

    Bill amount = ₹1000

    Maximum wallet amount that can be used = ₹200
    """

    __tablename__ = "wallet_discount_rules"

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "branch_id",
            name="uq_wallet_discount_rule_client_branch",
        ),
    )

    # =========================================================
    # PRIMARY KEY
    # =========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =========================================================
    # CLIENT
    # =========================================================

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # BRANCH
    # =========================================================

    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # MAX WALLET PAYMENT %
    # =========================================================

    max_wallet_discount_percent = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # =========================================================
    # STATUS
    # =========================================================

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # =========================================================
    # DATES
    # =========================================================

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