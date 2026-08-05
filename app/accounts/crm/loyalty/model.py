"""
app/accounts/crm/loyalty/model.py

SQLAlchemy Models for Customer Loyalty Accounts & Loyalty Transaction History.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Text
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class CustomerLoyaltyAccount(Base):
    __tablename__ = "customer_loyalty_accounts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    
    total_points_earned = Column(Float, default=0.0, nullable=False)
    total_points_redeemed = Column(Float, default=0.0, nullable=False)
    current_points_balance = Column(Float, default=0.0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer")
    transactions = relationship("LoyaltyTransaction", back_populates="account", cascade="all, delete-orphan")


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("customer_loyalty_accounts.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True, index=True)
    
    transaction_type = Column(String(50), nullable=False)  # "EARNED", "REDEEMED", "EXPIRED", "ADJUSTMENT"
    points = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account = relationship("CustomerLoyaltyAccount", back_populates="transactions")
    customer = relationship("Customer")
    bill = relationship("Bill")
