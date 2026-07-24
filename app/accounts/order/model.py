from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    DateTime
)

from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


# =========================================================
# ORDER MODEL
# =========================================================

class Order(Base):

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id")
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id")
    )

    table_id = Column(
        Integer,
        ForeignKey("tables.id")
    )

    order_type = Column(String, nullable=False)

    customer_name = Column(String)

    customer_phone = Column(String)

    notes = Column(String)

    status = Column(
        String,
        default="pending"
    )

    total_amount = Column(
        Float,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id")
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    client = relationship("Client")

    branch = relationship("Branch")

    table = relationship("Table")

    # customer = relationship("Customer")

    customer = relationship(
        "Customer",
        back_populates="orders",
        foreign_keys=[customer_id]
    )

    # ✅ IMPORTANT FIX
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )


# =========================================================
# ORDER ITEM MODEL
# =========================================================

class OrderItem(Base):

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id")
    )

    item_id = Column(
        Integer,
        ForeignKey("items.id")
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=True
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    # ✅ ITEM LEVEL STATUS
    order_status = Column(
        String,
        default="pending"
    )

    unit_price = Column(
        Float,
        nullable=False
    )

    discount_percent = Column(
        Float,
        default=0
    )

    tax_percent = Column(
        Float,
        default=0
    )

    subtotal = Column(
        Float,
        default=0
    )

    tax_amount = Column(
        Float,
        default=0
    )

    total_price = Column(
        Float,
        default=0
    )

    # ✅ IMPORTANT FIX
    order = relationship(
        "Order",
        back_populates="order_items"
    )

    item = relationship(
        "Item",
        back_populates="order_items"
    )

    customer = relationship("Customer")

    @property
    def price(self):

        if self.quantity:
            return round(
                self.total_price / self.quantity,
                2
            )

        base = self.unit_price or 0.0

        disc = self.discount_percent or 0.0

        tax = self.tax_percent or 0.0

        discounted = base - (
            base * disc / 100
        )

        return round(
            discounted + (
                discounted * tax / 100
            ),
            2
        )