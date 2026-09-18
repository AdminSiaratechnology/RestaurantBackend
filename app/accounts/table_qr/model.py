import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class TableQRCode(Base):
    __tablename__ = "table_qr_codes"

    id = Column(
        Integer,
        primary_key=True,
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

    table_id = Column(
        Integer,
        ForeignKey("tables.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    qr_token = Column(
        String(255),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
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

    client = relationship("Client")
    branch = relationship("Branch")
    table = relationship("Table")


class RestaurantSession(Base):
    __tablename__ = "restaurant_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_token_hash = Column(
        String(64),
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

    table_id = Column(
        Integer,
        ForeignKey("tables.id"),
        nullable=False,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )

    status = Column(
        String(20),
        default=SessionStatus.ACTIVE.value,
        server_default="active",
        nullable=False,
        index=True,
    )

    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    ended_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    client = relationship("Client")
    branch = relationship("Branch")
    table = relationship("Table")
    customer = relationship("Customer")
    orders = relationship("Order", back_populates="restaurant_session")
