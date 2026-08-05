from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Customer(Base):

    __tablename__ = "customers"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # =====================================================
    # BASIC DETAILS
    # =====================================================

    name = Column(
        String,
        nullable=False
    )

    phone = Column(
        String,
        nullable=False,
        index=True
    )

    email = Column(
        String,
        nullable=True,
        index=True
    )

    address = Column(
        String,
        nullable=True
    )

    gender = Column(
        String,
        nullable=True
    )

    dob = Column(
        Date,
        nullable=True
    )

    anniversary = Column(
        Date,
        nullable=True
    )

    profile_photo = Column(
        String,
        nullable=True
    )

    remarks = Column(
        String,
        nullable=True
    )

    # =====================================================
    # CRM DETAILS
    # =====================================================

    customer_source = Column(
        String,
        default="Walk-In",
        nullable=False
    )

    customer_type = Column(
        String,
        default="Regular",
        nullable=False
    )

    status = Column(
        String,
        default="Active",
        nullable=False
    )

    current_rank = Column(
        String,
        default="Bronze",
        nullable=False,
        index=True
    )

    is_vip = Column(
        Boolean,
        default=False,
        nullable=False
    )

    preferred_language = Column(
        String,
        default="English",
        nullable=False
    )

    preferred_contact = Column(
        String,
        default="WhatsApp",
        nullable=False
    )

    marketing_opt_in = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # =====================================================
    # VISIT DETAILS
    # =====================================================

    first_visit_at = Column(
        DateTime,
        nullable=True
    )

    last_visit_at = Column(
        DateTime,
        nullable=True
    )

    last_order_amount = Column(
        Integer,
        default=0,
        nullable=False
    )

    # =====================================================
    # CUSTOMER ANALYTICS (FAST ACCESS)
    # =====================================================

    total_orders = Column(
        Integer,
        default=0,
        nullable=False
    )

    total_visits = Column(
        Integer,
        default=0,
        nullable=False
    )

    total_spend = Column(
        Integer,
        default=0,
        nullable=False
    )

    average_order_value = Column(
        Integer,
        default=0,
        nullable=False
    )

    # =====================================================
    # CAMPAIGN INFO
    # =====================================================

    last_campaign_at = Column(
        DateTime,
        nullable=True
    )

    birthday_wish_sent = Column(
        Boolean,
        default=False,
        nullable=False
    )

    anniversary_wish_sent = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # =====================================================
    # RELATIONS
    # =====================================================

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

    branch_name = Column(
        String,
        nullable=True
    )

    last_order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=True
    )

    # =====================================================
    # DATES
    # =====================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    __table_args__ = (
        UniqueConstraint(
            "phone",
            "client_id",
            name="uq_customer_phone_per_client"
        ),
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    orders = relationship(
        "Order",
        back_populates="customer",
        foreign_keys="Order.customer_id"
    )

    last_order = relationship(
        "Order",
        foreign_keys=[last_order_id],
        primaryjoin="Customer.last_order_id == Order.id",
        uselist=False
    )

    customer_visit_history = relationship(
        "CustomerVisitHistory",
        back_populates="customer",
        cascade="all, delete-orphan"
    )