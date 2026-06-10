
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime,
    UniqueConstraint
)

from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)

    partner_id = Column(
        Integer,
        ForeignKey("partners.id"),
        nullable=False
    )

    # ✅ NEW
    # code = Column(String(20), nullable=False)

    name = Column(String, nullable=False)

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    password_hash = Column(String, nullable=False)

    role = Column(String, default="client")

    slug = Column(
        String,
        unique=True,
        index=True
    )

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # 🔗 Relationships
    partner = relationship(
        "Partner",
        back_populates="clients"
    )

    brands = relationship(
        "Brand",
        back_populates="client"
    )

    branches = relationship(
        "Branch",
        back_populates="client"
    )

    pricings = relationship(
        "Pricing",
        back_populates="client"
    )

    orders = relationship(
        "Order",
        back_populates="client"
    )

    items = relationship(
        "Item",
        back_populates="client"
    )

    staffs = relationship(
        "Staff",
        back_populates="client"
    )

    tax_settings = relationship(
        "TaxBillingSetting",
        back_populates="client"
    )