from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime
)

from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class CustomerVisitHistory(Base):

    __tablename__ = "customer_visit_history"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # =====================================================
    # RELATIONS
    # =====================================================

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=True
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id"),
        nullable=True
    )

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

    # =====================================================
    # VISIT INFO
    # =====================================================

    visit_date = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    total_amount = Column(Float, default=0)
    discount = Column(Float, default=0)
    tax = Column(Float, default=0)
    # net_amount = Column(Float, default=0)

    payment_method = Column(String, nullable=True)
    table_name = Column(String, nullable=True)
    visit_type = Column(String, nullable=True)

    # =====================================================
    # DATES
    # =====================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    # back_populates target already exists on your Customer model
    # as `customer_visit_history` — no change needed there.
    customer = relationship(
        "Customer",
        back_populates="customer_visit_history"
    )
