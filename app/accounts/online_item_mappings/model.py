# app/online_item_mappings/model.py

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OnlinePlatformItemMapping(Base):
    __tablename__ = "online_platform_item_mappings"

    __table_args__ = (
        # One internal item can only be mapped once
        # per online platform connection
        UniqueConstraint(
            "online_platform_connection_id",
            "item_id",
            name="uq_online_platform_connection_item",
        ),

        # One platform item ID can only point to one
        # internal item for the same connection
        UniqueConstraint(
            "online_platform_connection_id",
            "platform_item_id",
            name="uq_online_platform_connection_platform_item",
        ),

        Index(
            "ix_online_platform_item_mappings_connection_id",
            "online_platform_connection_id",
        ),

        Index(
            "ix_online_platform_item_mappings_item_id",
            "item_id",
        ),

        Index(
            "ix_online_platform_item_mappings_platform_item_id",
            "platform_item_id",
        ),

        Index(
            "ix_online_platform_item_mappings_is_active",
            "is_active",
        ),
    )

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =====================================================
    # PLATFORM CONNECTION
    # =====================================================

    online_platform_connection_id: Mapped[int] = mapped_column(
        ForeignKey(
            "online_platform_connections.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # =====================================================
    # INTERNAL ITEM
    # =====================================================

    item_id: Mapped[int] = mapped_column(
        ForeignKey(
            "items.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # =====================================================
    # PLATFORM ITEM
    # =====================================================

    platform_item_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    platform_item_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # =====================================================
    # STATUS
    # =====================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # =====================================================
    # OPTIONAL NOTES
    # =====================================================

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    online_platform_connection = relationship(
        "OnlinePlatformConnection",
        back_populates="item_mappings",
    )

    item = relationship(
        "Item",
        back_populates="online_platform_mappings",
    )