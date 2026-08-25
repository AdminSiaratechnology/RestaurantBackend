from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# =====================================================
# CUSTOMER TYPE ENUM
# =====================================================

class CustomerTypeEnum(str, PyEnum):
    NEW = "New"
    REGULAR = "Regular"
    VIP = "VIP"


class Customer(Base):

    __tablename__ = "customers"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =====================================================
    # BASIC DETAILS
    # =====================================================

    name = Column(
        String,
        nullable=False,
    )

    phone = Column(
        String,
        nullable=True,
        index=True,
    )

    email = Column(
        String,
        nullable=True,
        index=True,
    )

    address = Column(
        String,
        nullable=True,
    )

    gender = Column(
        String,
        nullable=True,
    )

    dob = Column(
        Date,
        nullable=True,
    )

    anniversary = Column(
        Date,
        nullable=True,
    )

    profile_photo = Column(
        String,
        nullable=True,
    )

    remarks = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # CRM DETAILS
    # =====================================================

    customer_source = Column(
        String,
        default="Walk-In",
        nullable=False,
    )

    # =====================================================
    # CUSTOMER TYPE
    #
    # Automatically calculated:
    #
    # Gold rank          -> VIP
    # 1 or 2 visits      -> New
    # More than 2 visits -> Regular
    #
    # DO NOT update this manually.
    # =====================================================

    customer_type = Column(
        SQLEnum(
            CustomerTypeEnum,
            name="customer_type_enum",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        default=CustomerTypeEnum.NEW,
        nullable=False,
    )

    status = Column(
        String,
        default="Active",
        nullable=False,
    )

    current_rank = Column(
        String,
        default="Bronze",
        nullable=False,
        index=True,
    )

    is_vip = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    preferred_language = Column(
        String,
        default="English",
        nullable=False,
    )

    preferred_contact = Column(
        String,
        default="WhatsApp",
        nullable=False,
    )

    marketing_opt_in = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    # =====================================================
    # VISIT DETAILS
    # =====================================================

    first_visit_at = Column(
        DateTime,
        nullable=True,
    )

    last_visit_at = Column(
        DateTime,
        nullable=True,
    )

    last_order_amount = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # =====================================================
    # CUSTOMER ANALYTICS
    # =====================================================

    total_orders = Column(
        Integer,
        default=0,
        nullable=False,
    )

    total_visits = Column(
        Integer,
        default=0,
        nullable=False,
    )

    # =====================================================
    # LIFETIME SPEND
    #
    # NEVER decreases on redemption.
    # Used for rank calculation.
    # =====================================================

    total_spend = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # =====================================================
    # CURRENT SPEND
    # =====================================================

    current_spend = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    average_order_value = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    # =====================================================
    # CAMPAIGN INFO
    # =====================================================

    last_campaign_at = Column(
        DateTime,
        nullable=True,
    )

    birthday_wish_sent = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    anniversary_wish_sent = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # RELATIONS
    # =====================================================

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

    branch_name = Column(
        String,
        nullable=True,
    )

    last_order_id = Column(
        Integer,
        ForeignKey("orders.id", use_alter=True),
        nullable=True,
    )

    # =====================================================
    # LOYALTY
    # =====================================================

    loyalty_points = Column(
        Float,
        default=0.0,
        nullable=False,
    )

    redeem_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # =====================================================
    # WALLET
    # =====================================================

    wallet_balance = Column(
        Float,
        default=0.0,
        nullable=False,
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

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    __table_args__ = (
        UniqueConstraint(
            "phone",
            "client_id",
            name="uq_customer_phone_per_client",
        ),
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    orders = relationship(
        "Order",
        back_populates="customer",
        foreign_keys="Order.customer_id",
    )

    last_order = relationship(
        "Order",
        foreign_keys=[last_order_id],
        primaryjoin="Customer.last_order_id == Order.id",
        uselist=False,
    )

    customer_visit_history = relationship(
        "CustomerVisitHistory",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    notes = relationship(
        "CustomerNote",
        back_populates="customer",
        foreign_keys="CustomerNote.customer_id",
        cascade="all, delete-orphan",
    )