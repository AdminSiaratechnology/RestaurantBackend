from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from enum import Enum

class statusEnum(str, Enum):
    active = "active"
    inactive = "inactive"



class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    status = Column(String, nullable=False, default=statusEnum.active.value)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    branch_code = Column(String(5),unique=True,nullable=False,index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ relationships
    client = relationship("Client", back_populates="branches")
    brand = relationship("Brand", back_populates="branches")

    tables = relationship("Table", back_populates="branch")  
    orders = relationship("Order", back_populates="branch")
    pricings = relationship("Pricing", back_populates="branch")
    categories = relationship("Category", back_populates="branch")
    items = relationship("Item", back_populates="branch")
    tax_settings = relationship("TaxBillingSetting", back_populates="branch", uselist=False)

    legal_compliance = relationship(
    "LegalCompliance",
    back_populates="branch",
    uselist=False
)