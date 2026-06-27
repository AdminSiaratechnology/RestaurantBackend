from datetime import datetime
from typing import Optional
from app.accounts.vendor.enum import PaymentMethod, VendorStatus, VendorType
from pydantic import BaseModel, EmailStr



class VendorCreate(BaseModel):

    # Basic
    vendor_name: str
    vendor_type: VendorType

    # Contact
    contact_person: Optional[str] = None
    mobile: str
    email: Optional[EmailStr] = None

    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

    # Tax
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    fssai_number: Optional[str] = None

    # Banking
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None

    # Payment
    payment_method: Optional[PaymentMethod] = None
    credit_days: int = 0
    credit_limit: float = 0

    # Business
    product_categories: Optional[str] = None
    branch_id: Optional[int] = None

    preferred_vendor: bool = False
    lead_time_days: int = 0

    notes: Optional[str] = None


class VendorUpdate(BaseModel):

    vendor_name: Optional[str] = None
    vendor_type: Optional[VendorType] = None

    contact_person: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    fssai_number: Optional[str] = None

    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None

    payment_method: Optional[PaymentMethod] = None
    credit_days: Optional[int] = None
    credit_limit: Optional[float] = None

    product_categories: Optional[str] = None
    branch_id: Optional[int] = None

    preferred_vendor: Optional[bool] = None
    lead_time_days: Optional[int] = None

    notes: Optional[str] = None

    status: Optional[VendorStatus] = None


class VendorResponse(BaseModel):

    id: int
    vendor_code: str

    vendor_name: str
    vendor_type: VendorType

    contact_person: Optional[str]
    mobile: str
    email: Optional[str]

    city: Optional[str]
    state: Optional[str]

    gstin: Optional[str]

    payment_method: Optional[PaymentMethod]
    credit_days: int
    credit_limit: float

    product_categories: Optional[str]

    status: VendorStatus

    created_at: datetime

    class Config:
        from_attributes = True