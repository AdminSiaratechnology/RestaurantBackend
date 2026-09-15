import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import relationship

from app.db.base import Base


# =========================================================
# ONLINE PLATFORM
# =========================================================

class OnlinePlatform(str, enum.Enum):

    SWIGGY = "swiggy"

    ZOMATO = "zomato"

    UBER_EATS = "uber_eats"

    DOORDASH = "doordash"

    DELIVEROO = "deliveroo"

    TALABAT = "talabat"

    OTHER = "other"


# =========================================================
# ONLINE ORDER STATUS
# =========================================================

class OnlineOrderStatus(str, enum.Enum):

    PENDING = "pending"

    ACCEPTED = "accepted"

    REJECTED = "rejected"

    READY_FOR_PICKUP = "ready_for_pickup"

    PICKED_UP = "picked_up"

    OUT_FOR_DELIVERY = "out_for_delivery"

    DELIVERED = "delivered"

    CANCELLED = "cancelled"


# =========================================================
# ONLINE ORDER DETAIL
# =========================================================

class OnlineOrderDetail(Base):

    __tablename__ = "online_order_details"

    id = Column(
        Integer,
        primary_key=True,
    )

    # =====================================================
    # RMS ORDER
    # =====================================================

    order_id = Column(
        Integer,
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    # =====================================================
    # PLATFORM
    # =====================================================

    platform = Column(
        Enum(
            OnlinePlatform,
            values_callable=lambda enum: [
                e.value
                for e in enum
            ],
            name="online_platform_enum",
            native_enum=True,
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # EXTERNAL ORDER ID
    # =====================================================

    external_order_id = Column(
        String(255),
        nullable=False,
    )

    external_order_number = Column(
        String(255),
        nullable=True,
    )

    # =====================================================
    # DELIVERY STATUS
    # =====================================================

    online_status = Column(
        Enum(
            OnlineOrderStatus,
            values_callable=lambda enum: [
                e.value
                for e in enum
            ],
            name="online_order_status_enum",
            native_enum=True,
        ),
        nullable=False,
        default=OnlineOrderStatus.PENDING,
        server_default="pending",
        index=True,
    )

    # =====================================================
    # REJECTION
    # =====================================================

    rejection_reason = Column(
        String(100),
        nullable=True,
    )

    rejection_note = Column(
        Text,
        nullable=True,
    )

    # =====================================================
    # PLATFORM ORIGINAL DATA
    # =====================================================

    raw_payload = Column(
        JSON,
        nullable=True,
    )

    platform_metadata = Column(
        JSON,
        nullable=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    received_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    ready_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    picked_up_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    out_for_delivery_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivered_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

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

    # =====================================================
    # RELATIONSHIP
    # =====================================================

    order = relationship(
        "Order",
        back_populates="online_order_detail",
    )

    # =====================================================
    # PREVENT DUPLICATE PLATFORM ORDERS
    # =====================================================

    __table_args__ = (

        UniqueConstraint(
            "platform",
            "external_order_id",
            name="uq_online_platform_external_order",
        ),

    )