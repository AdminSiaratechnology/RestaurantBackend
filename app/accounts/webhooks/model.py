import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.base import Base


# =========================================================
# WEBHOOK EVENT STATUS
# =========================================================

class WebhookEventStatus(str, enum.Enum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# =========================================================
# WEBHOOK EVENT
# =========================================================

class WebhookEvent(Base):

    __tablename__ = "webhook_events"

    id = Column(
        Integer,
        primary_key=True,
    )

    # =====================================================
    # PLATFORM
    # =====================================================

    platform = Column(
        String(100),
        nullable=False,
        index=True,
    )

    # =====================================================
    # EVENT ID
    # =====================================================

    event_id = Column(
        String(255),
        nullable=False,
    )

    # =====================================================
    # EVENT TYPE
    # =====================================================

    event_type = Column(
        String(100),
        nullable=True,
    )

    # =====================================================
    # RELATED ORDER
    # =====================================================

    external_order_id = Column(
        String(255),
        nullable=True,
        index=True,
    )

    order_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    # =====================================================
    # EVENT STATUS
    # =====================================================

    status = Column(
        Enum(
            WebhookEventStatus,
            name="webhook_event_status_enum",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
            native_enum=True,
        ),
        nullable=False,
        default=WebhookEventStatus.PROCESSING,
        server_default="processing",
        index=True,
    )

    # =====================================================
    # PAYLOAD
    # =====================================================

    payload = Column(
        JSON,
        nullable=True,
    )

    # =====================================================
    # ERROR
    # =====================================================

    error_message = Column(
        Text,
        nullable=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    processed_at = Column(
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
    # DATABASE IDEMPOTENCY
    # =====================================================

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "event_id",
            name="uq_webhook_event_platform_event_id",
        ),
    )