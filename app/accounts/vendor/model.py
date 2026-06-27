from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    ForeignKey
)
from datetime import datetime
from app.accounts.vendor.enum import PaymentMethod, VendorStatus, VendorType
from app.db.base import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)

    # Basic Information
    vendor_code = Column(String, unique=True, nullable=False)
    vendor_name = Column(String, nullable=False)

    vendor_type = Column(String)  # Supplier, Manufacturer, Distributor

    status = Column(
        String,
        default="active"
    )

    # Contact Information
    contact_person = Column(String)

    mobile = Column(String, nullable=False)

    email = Column(String)

    # Address Information
    address = Column(String)

    city = Column(String)

    state = Column(String)

    pincode = Column(String)

    # Tax Information
    gstin = Column(String)

    pan_number = Column(String)

    fssai_number = Column(String)

    # Banking Information
    bank_name = Column(String)

    account_number = Column(String)

    ifsc_code = Column(String)

    # Payment Information
    payment_method = Column(String)
    # Cash, Bank Transfer, UPI, Cheque

    credit_days = Column(Integer, default=0)

    credit_limit = Column(Float, default=0)

    # Business Information
    product_categories = Column(String)
    # Vegetables, Dairy, Meat, Grocery etc.

    preferred_vendor = Column(
        Boolean,
        default=False
    )

    lead_time_days = Column(
        Integer,
        default=0
    )

    # Branch Mapping
    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=True
    )

    # Financial Tracking
    current_outstanding = Column(
        Float,
        default=0
    )

    total_purchase_amount = Column(
        Float,
        default=0
    )

    last_purchase_date = Column(
        DateTime,
        nullable=True
    )

    # Additional Information
    notes = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )