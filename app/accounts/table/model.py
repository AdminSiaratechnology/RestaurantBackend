from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
import enum
from sqlalchemy import Enum as PgEnum


class TableShape(str, enum.Enum):
    rectangular = "rectangular"
    round = "round"
    square = "square"
    oval = "oval"


class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)

    name = Column(String, nullable=False)
    floor = Column(String, nullable=True)
    number_of_seats = Column(Integer, nullable=False)

    # ✅ FIXED (inside class)
    shape = Column(
        PgEnum(TableShape, name="tableshape"),
        default=TableShape.rectangular
    )

    status = Column(String, default="available")
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ RELATIONSHIP
    branch = relationship("Branch", back_populates="tables")