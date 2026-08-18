"""
CRM Wallet Models.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.db.base import Base


# ============================================================
# CUSTOMER WALLET ACCOUNT
# ============================================================


class CustomerWalletAccount(Base):

    __tablename__ = "customer_wallet_accounts"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # One customer = one wallet
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
    # CURRENT BALANCE
    # ========================================================

    balance = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    # ========================================================
    # TOTAL RECHARGED
    # ========================================================

    total_recharged = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    # ========================================================
    # TOTAL SPENT
    # ========================================================

    total_spent = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    # ========================================================
    # ACTIVE
    # ========================================================

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # ========================================================
    # TIMESTAMPS
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


# ============================================================
# WALLET TRANSACTION
# ============================================================


class WalletTransaction(Base):

    __tablename__ = "wallet_transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    wallet_account_id = Column(
        Integer,
        ForeignKey(
            "customer_wallet_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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
        nullable=True,
        index=True,
    )

    # CREDIT / DEBIT
    transaction_type = Column(
        String(30),
        nullable=False,
    )

    amount = Column(
        Float,
        nullable=False,
    )

    balance_before = Column(
        Float,
        nullable=False,
    )

    balance_after = Column(
        Float,
        nullable=False,
    )

    # BILL / LOYALTY_CONVERSION / RECHARGE etc.
    reference_type = Column(
        String(50),
        nullable=True,
    )

    reference_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )