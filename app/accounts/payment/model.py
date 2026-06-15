from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Text
)

from datetime import datetime
from sqlalchemy import JSON

from app.db.base import Base


class Payment(Base):

    __tablename__ = "payments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id"),
        nullable=False
    )

    payment_method = Column(
        String,
        nullable=False
    )


    payment_breakdown = Column(
        JSON,
        nullable=True
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False
    )

    payment_method = Column(
        String,
        nullable=False
    )

    bill_amount = Column(
        Float,
        nullable=False
    )

    receive_amount = Column(
        Float,
        nullable=False
    )

    paid_amount = Column(
        Float,
        nullable=False
    )

    change_amount = Column(
        Float,
        default=0
    )

    payment_reference = Column(
        String,
        nullable=True
    )

    notes = Column(
        Text,
        nullable=True
    )

    # Offer information
    offer_id = Column(
        Integer,
        ForeignKey("offers.id"),
        nullable=True
    )

    offer_discount = Column(
        Float,
        default=0
    )

    payment_date = Column(
        DateTime,
        default=datetime.utcnow
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )