# from sqlalchemy import Column, Enum, Float, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
# from sqlalchemy.orm import relationship
# from datetime import datetime
# from app.db.base import Base
# from slugify import slugify


# class Admin(Base):
#     __tablename__ = "admin"

#     id = Column(Integer, primary_key=True)

#     partner_id = Column(Integer, ForeignKey("partners.id"), nullable=False)  # ✅ ADD THIS

#     name = Column(String, nullable=False)
#     email = Column(String, unique=True, index=True, nullable=False)
#     password_hash = Column(String, nullable=False)
#     role = Column(String, default="admin")
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=datetime.utcnow)

#     # 🔗 Relationships
#     partner = relationship("Partner", back_populates="clients", cascade="all, delete")  # ✅ FIXED (same issue avoided)
    