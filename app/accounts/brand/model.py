from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("client_id", "slug", name="uq_brand_slug_per_client"),
    )

    orders = relationship("Order", back_populates="brand")

    # ✅ correct
    client = relationship("Client", back_populates="brands")
    branches = relationship("Branch", back_populates="brand")