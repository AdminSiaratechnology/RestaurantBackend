"""
app/accounts/crm/wallet/model.py

SQLAlchemy Models for Customer Wallet Accounts
and Wallet Transaction History.
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
# CUSTOMER WALLET ACCOUNT
# ============================================================


class CustomerWalletAccount(Base):

    __tablename__ = "customer_wallet_accounts"

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
    # WALLET BALANCE
    # ========================================================

    balance = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Money manually recharged into wallet.
    #
    # Loyalty conversion does NOT increase this.
    # ========================================================

    total_recharged = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Money spent from wallet.
    # ========================================================

    total_spent = Column(
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
        "WalletTransaction",
        back_populates="account",
        cascade="all, delete-orphan",
    )


# ============================================================
# WALLET TRANSACTION
# ============================================================


class WalletTransaction(Base):

    __tablename__ = "wallet_transactions"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # WALLET ACCOUNT
    # ========================================================

    account_id = Column(
        Integer,
        ForeignKey(
            "customer_wallet_accounts.id",
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

    # CREDIT
    # DEBIT
    # CASHBACK
    # REFUND
    # LOYALTY_CONVERSION
    #
    transaction_type = Column(
        String(50),
        nullable=False,
    )

    # ========================================================
    # AMOUNT
    # ========================================================

    amount = Column(
        Float,
        nullable=False,
    )

    # ========================================================
    # BALANCE AFTER
    # ========================================================

    balance_after = Column(
        Float,
        nullable=False,
    )

    # ========================================================
    # REMARKS
    # ========================================================

    remarks = Column(
        Text,
        nullable=True,
    )

    # ========================================================
    # DATE
    # ========================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    account = relationship(
        "CustomerWalletAccount",
        back_populates="transactions",
    )

    customer = relationship(
        "Customer",
    )

    bill = relationship(
        "Bill",
    )