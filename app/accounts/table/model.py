from enum import Enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship
from app.accounts.table.enum import TableShape, TableStatus
from app.db.base import Base

class TableStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    reserved = "reserved"



class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)

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

    name = Column(String, nullable=False)

    floor = Column(String, nullable=True)

    number_of_seats = Column(Integer, nullable=False)

    shape = Column(
        PgEnum(TableShape, name="tableshape"),
        default=TableShape.rectangular
    )

    status = Column(
        PgEnum(TableStatus, name="tablestatus"),
        default=TableStatus.available
    )

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # ── Floor Layout / Canvas Position Fields ──────────────────────────────
    # These are purely visual positioning fields for the Floor Layout canvas.
    # They have NO effect on orders, billing, QR, sessions, or table status.
    # All nullable — tables without saved positions are auto-placed on canvas.

    pos_x = Column(Float, nullable=True)          # Canvas X position (px)
    pos_y = Column(Float, nullable=True)          # Canvas Y position (px)
    rotation = Column(Float, nullable=True, default=0.0)  # Rotation degrees (0–360)
    layout_width = Column(Float, nullable=True)   # Canvas display width (px)
    layout_height = Column(Float, nullable=True)  # Canvas display height (px)

    # ──────────────────────────────────────────────────────────────────────

    branch = relationship(
        "Branch",
        back_populates="tables"
    )