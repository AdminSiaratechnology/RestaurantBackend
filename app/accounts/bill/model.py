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

from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.accounts.bill.enum import PaymentStatus


class Bill(Base):
    __tablename__ = "bills"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =====================================================
    # RELATIONS
    # =====================================================

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )

    # =====================================================
    # BILL INFO
    # =====================================================

    invoice_no = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    order_type = Column(
        String,
        nullable=False,
    )

    customer_name = Column(
        String,
        nullable=True,
    )

    customer_phone = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # PAYMENT
    # =====================================================

    payment_status = Column(
        PgEnum(
            PaymentStatus,
            name="paymentstatus",
        ),
        default=PaymentStatus.pending,
        nullable=False,
    )

    payment_method = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # BILL AMOUNTS
    # =====================================================

    subtotal = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    cgst_percent = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    cgst_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    sgst_percent = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    sgst_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    service_charge_percent = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    service_charge_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    tax_total = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # General/manual discount
    discount_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    round_off_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Total before offer
    grand_total = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Offer
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

    # Final amount customer should pay
    final_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    paid_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    due_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # =====================================================
    # EXTRA
    # =====================================================

    notes = Column(
        Text,
        nullable=True,
    )

    footer_message = Column(
        Text,
        nullable=True,
    )

    # =====================================================
    # DATES
    # =====================================================

    billed_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
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

    is_edited = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    order = relationship(
        "Order",
        lazy="selectin",
    )

    client = relationship(
        "Client",
        lazy="selectin",
    )

    branch = relationship(
        "Branch",
        lazy="selectin",
    )

    offer = relationship(
        "Offer",
        lazy="selectin",
    )

    customer = relationship(
        "Customer",
        lazy="selectin",
    )


    wallet_discount = Column(
        Float,
        default=0.0,
        nullable=False,
    )