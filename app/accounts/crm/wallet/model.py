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
    UniqueConstraint,
)

from app.db.base import Base


class CustomerWalletAccount(Base):
    """
    One wallet account per CRM customer.

    Example:

        customer_id = 25
        balance = ₹500
    """

    __tablename__ = "customer_wallet_accounts"

    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            name="uq_customer_wallet_account_customer",
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
    # CUSTOMER
    # =====================================================

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

    # =====================================================
    # CLIENT
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
    # WALLET BALANCE
    # =====================================================

    balance = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # =====================================================
    # STATUS
    # =====================================================

    is_active = Column(
        # Boolean import karna ho to add karo
        # currently keeping integer-style compatibility
        Boolean,
        nullable=False,
        default=True,
    )

    # =====================================================
    # DATES
    # =====================================================

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


class WalletTransaction(Base):
    """
    CRM Wallet ledger.

    Every wallet movement is recorded here.

    CREDIT -> wallet balance increases
    DEBIT  -> wallet balance decreases
    REFUND -> wallet balance increases
    """

    __tablename__ = "wallet_transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer_id = Column(
        Integer,
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # WALLET ACCOUNT
    # =====================================================

    wallet_account_id = Column(
        Integer,
        ForeignKey(
            "customer_wallet_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # CLIENT
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
        nullable=True,
        index=True,
    )

    # =====================================================
    # TRANSACTION
    # =====================================================

    transaction_type = Column(
        String,
        nullable=False,
    )

    # CREDIT
    # DEBIT
    # REFUND

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

    # =====================================================
    # REFERENCE
    # =====================================================

    reference_type = Column(
        String,
        nullable=True,
    )

    # BILL
    # PAYMENT
    # MANUAL
    # REFUND

    reference_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    # =====================================================
    # NOTES
    # =====================================================

    notes = Column(
        Text,
        nullable=True,
    )

    # =====================================================
    # DATE
    # =====================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )