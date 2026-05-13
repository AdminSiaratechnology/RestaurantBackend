# app/models/offer.py

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from datetime import datetime
from app.db.base import Base


class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)

    title = Column(String, nullable=False)
    description = Column(String)

    discount_percent = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)

    valid_till = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)