# app/online_platforms/model.py

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OnlinePlatformConnection(Base):
    __tablename__ = "online_platform_connections"

    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "platform",
            name="uq_online_platform_branch_platform",
        ),
        Index(
            "ix_online_platform_connections_branch_id",
            "branch_id",
        ),
        Index(
            "ix_online_platform_connections_platform",
            "platform",
        ),
        Index(
            "ix_online_platform_connections_is_active",
            "is_active",
        ),
        Index(
            "ix_online_platform_connections_connection_status",
            "connection_status",
        ),
    )

    # =========================================================
    # PRIMARY KEY
    # =========================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =========================================================
    # BRANCH
    # =========================================================

    branch_id: Mapped[int] = mapped_column(
        ForeignKey(
            "branches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # =========================================================
    # PLATFORM
    # =========================================================

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    # =========================================================
    # CONNECTION STATUS
    # =========================================================

    connection_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # =========================================================
    # AUTH / CREDENTIALS
    # =========================================================

    api_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    api_secret: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    access_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    webhook_secret: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # =========================================================
    # PLATFORM IDENTIFIERS
    # =========================================================

    platform_restaurant_id: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    platform_store_id: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    # =========================================================
    # FLEXIBLE PLATFORM CONFIG
    # =========================================================

    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # =========================================================
    # ERROR / CONNECTION INFORMATION
    # =========================================================

    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    last_connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

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

    # =========================================================
    # RELATIONSHIP
    # =========================================================

    branch = relationship(
        "Branch",
        back_populates="online_platform_connections",
    )



    item_mappings = relationship(
        "OnlinePlatformItemMapping",
        back_populates="online_platform_connection",
        cascade="all, delete-orphan",
    )