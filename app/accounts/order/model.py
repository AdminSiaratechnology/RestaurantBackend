from sqlalchemy import DateTime   
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    branch_id = Column(Integer, ForeignKey("branches.id"))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))

    order_type = Column(String)
    customer_name = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    status = Column(String, default="pending")
    total_amount = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="orders")
    brand = relationship("Brand", back_populates="orders")
    branch = relationship("Branch", back_populates="orders")

    # ✅ ADD THIS (IMPORTANT FIX)
    order_items = relationship("OrderItem", back_populates="order") # ✅ ADD THIS

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)

    order_id = Column(Integer, ForeignKey("orders.id"))
    item_id = Column(Integer, ForeignKey("items.id"))

    quantity = Column(Integer, nullable=False)

    # snapshot pricing
    unit_price = Column(Float, nullable=False)

    discount_percent = Column(Float, default=0)

    tax_percent = Column(Float, default=0)

    subtotal = Column(Float, default=0)

    tax_amount = Column(Float, default=0)

    total_price = Column(Float, default=0)

    order = relationship("Order", back_populates="order_items")
    item = relationship("Item", back_populates="order_items")