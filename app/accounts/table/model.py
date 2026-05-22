from enum import Enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship

from app.accounts.table.schema import TableShape, TableStatus
from app.db.base import Base

class TableStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    reserved = "reserved"
    inactive = "inactive"



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

    branch = relationship(
        "Branch",
        back_populates="tables"
    )