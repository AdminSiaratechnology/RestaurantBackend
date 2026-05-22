from sqlalchemy import Column, Enum, Float, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
from slugify import slugify

class Pricing(Base):
    __tablename__ = "pricings"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"))
    price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=True, default=0.0)
    discount = Column(Float, nullable=True, default=0.0)  # percentage e.g. 10 = 10%
    tax_rate = Column(Float, nullable=True, default=5.0)   # percentage e.g. 5 = 5%
    calories = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # __table_args__ = (
    #     UniqueConstraint('client_id', 'item_id', name='unique_item_per_client'),
    # )

    # 🔗 Relationships
    item = relationship("Item", back_populates="pricings")
    client = relationship("Client", back_populates="pricings")
    branch = relationship("Branch", back_populates="pricings")