"""
app/accounts/crm/customer_history/model.py

Customer Visit History Model
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class CustomerVisitHistory(Base):

    __tablename__ = "customer_visit_history"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer_id = Column(
        Integer,
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # ORDER
    # =====================================================

    order_id = Column(
        Integer,
        ForeignKey(
            "orders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # BILL
    # =====================================================

    bill_id = Column(
        Integer,
        ForeignKey(
            "bills.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # CLIENT
    # =====================================================

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # BRANCH
    # =====================================================

    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # VISIT
    # =====================================================

    visit_date = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    # =====================================================
    # AMOUNTS
    # =====================================================

    total_amount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    discount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    tax = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # =====================================================
    # CURRENT SPEND SNAPSHOT
    # =====================================================
    #
    # This stores the customer's current_spend AFTER
    # this particular visit.
    #
    # Example:
    #
    # Visit 1:
    # bill = 2000
    # current_spend = 2000
    #
    # Visit 2:
    # bill = 3000
    # current_spend = 5000
    #
    # Later customer redeems:
    # Customer.current_spend = 0
    #
    # This history row MUST remain 5000.
    #

    current_spend = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # =====================================================
    # PAYMENT
    # =====================================================

    payment_method = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # TABLE
    # =====================================================

    table_name = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # VISIT TYPE
    # =====================================================

    visit_type = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # CREATED
    # =====================================================

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    customer = relationship(
        "Customer",
        back_populates="customer_visit_history",
    )