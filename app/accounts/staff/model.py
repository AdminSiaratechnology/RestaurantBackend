from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
import enum


# ✅ Role Enum
class StaffRole(str, enum.Enum):
    manager = "manager"
    waitr = "waiter"
    chef = "chef"


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    password_hash = Column(
        String,
        nullable=False
    )

    # ✅ Staff Role
    role = Column(
        Enum(StaffRole, name="staff_role_enum"),
        default=StaffRole.waitr,
        nullable=False
    )

    # ✅ Client Relation
    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False
    )

    # ✅ ADD THIS
    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ✅ Relationships
    client = relationship(
        "Client",
        back_populates="staffs"
    )

    # ✅ ADD THIS
    branch = relationship("Branch")

    permissions = relationship(
        "app.accounts.permission.model.StaffPermission",
        back_populates="staff",
        uselist=False
    )