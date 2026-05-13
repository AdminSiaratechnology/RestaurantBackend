# from sqlalchemy import Column, DateTime, ForeignKey, String, Integer, func
# from sqlalchemy.orm import relationship
# from app.db.base import Base


# class Tenant(Base):
#     __tablename__ = "tenants"

#     id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)
#     slug = Column(String, unique=True, index=True)  # 🔥 add index

#     admin_id = Column(Integer, ForeignKey("client.id"), nullable=False)

#     client = relationship("Client", back_populates="tenants")
#     brands = relationship("Brand", back_populates="tenant", cascade="all, delete")
#     branches = relationship("Branch", back_populates="tenant", cascade="all, delete")

#     created_at = Column(DateTime(timezone=True), server_default=func.now())