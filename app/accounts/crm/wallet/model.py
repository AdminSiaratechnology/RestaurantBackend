"""
app/accounts/crm/wallet/model.py

SQLAlchemy Models for Customer Wallet Accounts & Wallet Transaction History.
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


class CustomerWalletAccount(Base):
    __tablename__ = "customer_wallet_accounts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    
    balance = Column(Float, default=0.0, nullable=False)
    total_recharged = Column(Float, default=0.0, nullable=False)
    total_spent = Column(Float, default=0.0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer")
    transactions = relationship("WalletTransaction", back_populates="account", cascade="all, delete-orphan")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("customer_wallet_accounts.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True, index=True)
    
    transaction_type = Column(String(50), nullable=False)  # "CREDIT", "DEBIT", "CASHBACK", "REFUND"
    amount = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    remarks = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account = relationship("CustomerWalletAccount", back_populates="transactions")
    customer = relationship("Customer")
    bill = relationship("Bill")
