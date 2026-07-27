
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime
)
from app.db.base import Base

class CustomerVisitHistory(Base):

    __tablename__ = "customer_visit_history"

    id = Column(
        Integer,
        primary_key=True
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=True,
        index=True
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id"),
        nullable=True,
        index=True
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
        index=True
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
        index=True
    )

    visit_type = Column(
        String,
        nullable=False,
        default="Dine In"
    )

    visit_status = Column(
        String,
        default="Completed"
    )

    visit_date = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    total_amount = Column(
        Integer,
        default=0
    )

    discount = Column(
        Integer,
        default=0
    )

    tax = Column(
        Integer,
        default=0
    )

    payment_method = Column(
        String,
        nullable=True
    )

    table_name = Column(
        String,
        nullable=True
    )

    served_by = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    customer = relationship(
        "Customer",
        back_populates="customer_visit_history"
    )