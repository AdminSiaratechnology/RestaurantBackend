from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.db.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)

    client_id = Column(Integer, ForeignKey("clients.id"))
    branch_id = Column(Integer, ForeignKey("branches.id"))

    name = Column(String, nullable=False)
    row_category = Column(String)
    unit = Column(String)  # kg, liters, pieces

    stock_qty = Column(Float, default=0)
    reorder_level = Column(Float, default=0, nullable=True)

    cost_per_unit = Column(Float, default=0)

    vendor_name = Column(String, nullable=True)
    vendor_phone = Column(String, nullable=True)

    status = Column(String, default="in_stock")  
    # in_stock / low_stock / out_of_stock

    # last_restocked = Column(DateTime, nullable=True)
    # created_at = Column(DateTime, default=datetime.utcnow)
    last_restocked = Column(DateTime(timezone=True), nullable=True)
    # created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))