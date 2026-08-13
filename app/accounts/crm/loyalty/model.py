"""
app/accounts/crm/loyalty/model.py

SQLAlchemy Models for Customer Loyalty Accounts
and Loyalty Transaction History.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ============================================================
# CUSTOMER LOYALTY ACCOUNT
# ============================================================


class CustomerLoyaltyAccount(Base):

    __tablename__ = "customer_loyalty_accounts"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # CUSTOMER
    # ========================================================

    customer_id = Column(
        Integer,
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    # ========================================================
    # CLIENT
    # ========================================================

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ========================================================
    # POINTS
    # ========================================================

    # Lifetime points earned.
    #
    # NEVER reset during conversion.
    # ========================================================

    total_points_earned = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Lifetime points converted/redeemed.
    #
    # Every loyalty -> wallet conversion adds the
    # converted points here.
    # ========================================================

    total_points_redeemed = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Current available loyalty points.
    #
    # This becomes ZERO after every successful conversion.
    # ========================================================

    current_points_balance = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ========================================================
    # LEGACY / TRACKING FIELD
    # ========================================================

    converted_spend = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ========================================================
    # DATES
    # ========================================================

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

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    customer = relationship(
        "Customer",
    )

    transactions = relationship(
        "LoyaltyTransaction",
        back_populates="account",
        cascade="all, delete-orphan",
    )


# ============================================================
# LOYALTY TRANSACTION
# ============================================================


class LoyaltyTransaction(Base):

    __tablename__ = "loyalty_transactions"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # LOYALTY ACCOUNT
    # ========================================================

    account_id = Column(
        Integer,
        ForeignKey(
            "customer_loyalty_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ========================================================
    # CUSTOMER
    # ========================================================

    customer_id = Column(
        Integer,
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ========================================================
    # BILL
    # ========================================================

    bill_id = Column(
        Integer,
        ForeignKey(
            "bills.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # ========================================================
    # TRANSACTION TYPE
    # ========================================================

    # Examples:
    #
    # EARN
    # REDEEM
    # CONVERSION
    #
    # ========================================================

    transaction_type = Column(
        String(50),
        nullable=False,
    )

    # Positive for earning.
    # Negative for conversion/redeem.
    # ========================================================

    points = Column(
        Float,
        nullable=False,
    )

    # Balance immediately after transaction.
    # ========================================================

    balance_after = Column(
        Float,
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    account = relationship(
        "CustomerLoyaltyAccount",
        back_populates="transactions",
    )

    customer = relationship(
        "Customer",
    )

    bill = relationship(
        "Bill",
    )