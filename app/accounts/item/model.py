from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy import Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("name", "branch_id", name="uq_item_name_per_branch"),
    )

    client = relationship("Client", back_populates="items")
    category = relationship("Category", back_populates="items")
    branch = relationship("Branch", back_populates="items")

    pricings = relationship("Pricing", back_populates="item")
    order_items = relationship("OrderItem", back_populates="item")