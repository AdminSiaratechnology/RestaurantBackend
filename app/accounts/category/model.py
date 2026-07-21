from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, nullable=True)

    

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)  # ✅ ADD THIS

    created_at = Column(DateTime, default=datetime.utcnow)

    # relationships
    client = relationship("Client", backref="categories")
    branch = relationship("Branch", back_populates="categories")  # ✅ ADD THIS
    items = relationship("Item", back_populates="category")  # (if you use it)
    