from sqlalchemy import DateTime   
from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class Customer(Base):

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    phone = Column(String, nullable=False, index=True)

    email = Column(String, nullable=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=True
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=True
    )

    branch_name = Column(String, nullable=True)

    address = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "phone",
            "client_id",
            name="uq_customer_phone_per_client"
        ),
    )

    orders = relationship(
        "Order",
        back_populates="customer"
    )