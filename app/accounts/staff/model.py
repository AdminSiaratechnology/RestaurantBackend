from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Float
)

from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
import enum

class StaffRole(str, enum.Enum):
    manager = "manager"
    waiter = "waiter"
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

    gender = Column(String, nullable=True)

    phone_number = Column(String, nullable=True)

    # ✅ Staff Role
    role = Column(
        Enum(StaffRole, name="staff_role_enum"),
        default=StaffRole.waiter,
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

# =========================
# ADDRESS FIELDS
# =========================

    street_address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    pincode = Column(String, nullable=True)

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

 # =====================================
# Salary
# =====================================

    monthly_salary = Column(
        Float,
        nullable=True
    )

    hourly_rate = Column(
        Float,
        nullable=True
    )

# =====================================
# Government IDs
# =====================================

    aadhaar_number = Column(
        String(20),
        nullable=True
    )

    pan_number = Column(
        String(20),
        nullable=True
    )

# =====================================
# Banking
# =====================================

    bank_account = Column(
        String(50),
        nullable=True
    )

    ifsc_code = Column(
        String(20),
        nullable=True
)

    bank_name = Column(
        String(100),
        nullable=True
    )
