from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)

from app.db.base import Base


class Payment(Base):

    __tablename__ = "payments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id"),
        nullable=False,
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
    )

    # ========================================================
    # ACTUAL PAYMENT METHOD
    # ========================================================

    payment_method = Column(
        String,
        nullable=False,
    )

    # Example:
    #
    # [
    #   {
    #       "payment_method": "cash",
    #       "payment_amount": 4492.80
    #   }
    # ]
    #
    payment_breakdown = Column(
        JSON,
        nullable=True,
    )

    # ========================================================
    # ORIGINAL BILL AMOUNT
    # ========================================================

    bill_amount = Column(
        Float,
        nullable=False,
    )

    # ========================================================
    # ACTUAL MONEY RECEIVED
    # ========================================================

    receive_amount = Column(
        Float,
        nullable=False,
    )

    # ========================================================
    # FINAL PAYABLE AFTER DISCOUNTS
    # ========================================================

    paid_amount = Column(
        Float,
        nullable=False,
    )

    # ========================================================
    # CHANGE
    # ========================================================

    change_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    payment_reference = Column(
        String,
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    # ========================================================
    # OFFER
    # ========================================================

    offer_id = Column(
        Integer,
        ForeignKey("offers.id"),
        nullable=True,
    )

    offer_discount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ========================================================
    # CRM WALLET
    # ========================================================
    #
    # NOT A PAYMENT METHOD.
    #
    # This stores the amount deducted
    # from customer's CRM wallet.
    #
    # ========================================================

    wallet_discount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ========================================================
    # DATES
    # ========================================================

    payment_date = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )