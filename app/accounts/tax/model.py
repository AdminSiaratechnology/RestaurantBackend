from sqlalchemy import Column, Integer, Float, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class TaxBillingSetting(Base):
    __tablename__ = "tax_billing_settings"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, unique=True)

    # ── TAX FIELDS ──────────────────────────────────────────────
    default_tax_rate = Column(Float, default=5.0)
    cgst             = Column(Float, default=2.5)
    sgst             = Column(Float, default=2.5)
    service_charge   = Column(Float, default=0.0)

    # ── BILLING SETTINGS ────────────────────────────────────────
    bill_footer_message  = Column(Text,    default="Thank you for dining with us!")
    enable_service_charge = Column(Boolean, default=False)
    enable_tax            = Column(Boolean, default=True)
    round_off_bill        = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── RELATIONSHIPS ────────────────────────────────────────────
    client = relationship("Client", back_populates="tax_settings")
    branch = relationship("Branch", back_populates="tax_settings")
