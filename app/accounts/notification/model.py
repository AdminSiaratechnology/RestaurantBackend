# app/accounts/notification/model.py

import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.db.base import Base


class NotificationType(str, enum.Enum):
    # Order Events
    NEW_ORDER = "NEW_ORDER"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_PREPARING = "ORDER_PREPARING"
    ORDER_READY = "ORDER_READY"
    ORDER_SERVED = "ORDER_SERVED"
    ORDER_CANCELLED = "ORDER_CANCELLED"

    # Payment / Bill Events
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    BILL_REQUESTED = "BILL_REQUESTED"
    BILL_COMPLETED = "BILL_COMPLETED"

    # Customer Engagement & Marketing
    OFFER = "OFFER"
    PROMOTION = "PROMOTION"
    NEW_MENU = "NEW_MENU"
    ANNOUNCEMENT = "ANNOUNCEMENT"

    # CRM Loyalty & Wallet
    POINTS_EARNED = "POINTS_EARNED"
    POINTS_REDEEMED = "POINTS_REDEEMED"
    LOYALTY_UPDATE = "LOYALTY_UPDATE"
    RANK_UPGRADE = "RANK_UPGRADE"
    WALLET_CREDITED = "WALLET_CREDITED"


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    qr_session_id = Column(
        Integer,
        ForeignKey("restaurant_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    token = Column(String(512), nullable=False, unique=True, index=True)

    platform = Column(String(20), default="web", nullable=False)

    device_id = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    notifications_enabled = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("Client")
    branch = relationship("Branch")
    customer = relationship("Customer")
    staff = relationship("Staff")
    qr_session = relationship("RestaurantSession")


class CustomerNotificationPreference(Base):
    __tablename__ = "customer_notification_preferences"

    id = Column(Integer, primary_key=True, index=True)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_updates = Column(Boolean, default=True, nullable=False)
    payment_updates = Column(Boolean, default=True, nullable=False)
    offers = Column(Boolean, default=True, nullable=False)
    promotions = Column(Boolean, default=True, nullable=False)
    loyalty = Column(Boolean, default=True, nullable=False)
    new_menu = Column(Boolean, default=True, nullable=False)
    announcements = Column(Boolean, default=True, nullable=False)

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    customer = relationship("Customer")
    client = relationship("Client")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    qr_session_id = Column(
        Integer,
        ForeignKey("restaurant_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    offer_id = Column(
        Integer,
        ForeignKey("offers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)

    is_read = Column(Boolean, default=False, nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    read_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("Client")
    branch = relationship("Branch")
    customer = relationship("Customer")
    staff = relationship("Staff")
    order = relationship("Order")
    bill = relationship("Bill")
    offer = relationship("Offer")
    qr_session = relationship("RestaurantSession")
