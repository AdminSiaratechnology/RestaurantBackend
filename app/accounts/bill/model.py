from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Text
)

from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from datetime import datetime

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
        index=True
    )

    # =====================================================
    # RELATIONS
    # =====================================================

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
        unique=True
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False
    )

    # =====================================================
    # BILL INFO
    # =====================================================

    invoice_no = Column(
        String,
        unique=True,
        nullable=False
    )

    order_type = Column(
        String,
        nullable=False
    )

    customer_name = Column(
        String,
        nullable=True
    )

    customer_phone = Column(
        String,
        nullable=True
    )

    payment_status = Column(
    PgEnum(
        PaymentStatus,
        name="paymentstatus"
    ),
    default=PaymentStatus.pending,
    nullable=False
    )

    payment_method = Column(
        String,
        nullable=True
    )

    # =====================================================
    # BILL AMOUNTS
    # =====================================================

    subtotal = Column(
        Float,
        default=0
    )

    cgst_percent = Column(
        Float,
        default=0
    )

    cgst_amount = Column(
        Float,
        default=0
    )

    sgst_percent = Column(
        Float,
        default=0
    )

    sgst_amount = Column(
        Float,
        default=0
    )

    service_charge_percent = Column(
        Float,
        default=0
    )

    service_charge_amount = Column(
        Float,
        default=0
    )

    tax_total = Column(
        Float,
        default=0
    )

    discount_amount = Column(
        Float,
        default=0
    )

    round_off_amount = Column(
        Float,
        default=0
    )

    grand_total = Column(
        Float,
        default=0
    )

    paid_amount = Column(
        Float,
        default=0
    )

    due_amount = Column(
        Float,
        default=0
    )

    # =====================================================
    # EXTRA
    # =====================================================

    notes = Column(
        Text,
        nullable=True
    )

    footer_message = Column(
        Text,
        nullable=True
    )

    # =====================================================
    # DATES
    # =====================================================

    billed_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    order = relationship(
        "Order"
    )

    client = relationship(
        "Client"
    )

    branch = relationship(
        "Branch"
    )
    