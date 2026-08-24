from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from app.accounts.vendor.enum import (
    PaymentMethod,
    VendorStatus,
    VendorType,
)


# ============================================================
# CREATE
# ============================================================

class VendorCreate(BaseModel):

    vendor_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    vendor_type: VendorType = VendorType.supplier

    # --------------------------------------------------------
    # CONTACT
    # --------------------------------------------------------

    contact_person: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    mobile: str = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    email: Optional[EmailStr] = None

    # --------------------------------------------------------
    # ADDRESS
    # --------------------------------------------------------

    address: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    state: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    pincode: Optional[str] = Field(
        default=None,
        max_length=10,
    )

    # --------------------------------------------------------
    # TAX
    # --------------------------------------------------------

    gstin: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    pan_number: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    fssai_number: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    # --------------------------------------------------------
    # BANKING
    # --------------------------------------------------------

    bank_name: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    account_number: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    ifsc_code: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    payment_method: Optional[PaymentMethod] = None

    credit_days: int = Field(
        default=0,
        ge=0,
    )

    credit_limit: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )

    # --------------------------------------------------------
    # BUSINESS
    # --------------------------------------------------------

    product_categories: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    preferred_vendor: bool = False

    lead_time_days: int = Field(
        default=0,
        ge=0,
    )

    # --------------------------------------------------------
    # OPTIONAL BRANCH
    #
    # This is operational information only.
    # It is NOT the security boundary.
    # --------------------------------------------------------

    branch_id: Optional[int] = None

    # --------------------------------------------------------
    # NOTES
    # --------------------------------------------------------

    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


# ============================================================
# UPDATE
# ============================================================

class VendorUpdate(BaseModel):

    vendor_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    vendor_type: Optional[VendorType] = None

    # Contact

    contact_person: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    mobile: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=20,
    )

    email: Optional[EmailStr] = None

    # Address

    address: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    state: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    pincode: Optional[str] = Field(
        default=None,
        max_length=10,
    )

    # Tax

    gstin: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    pan_number: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    fssai_number: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    # Banking

    bank_name: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    account_number: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    ifsc_code: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    # Payment

    payment_method: Optional[PaymentMethod] = None

    credit_days: Optional[int] = Field(
        default=None,
        ge=0,
    )

    credit_limit: Optional[Decimal] = Field(
        default=None,
        ge=0,
    )

    # Business

    product_categories: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    preferred_vendor: Optional[bool] = None

    lead_time_days: Optional[int] = Field(
        default=None,
        ge=0,
    )

    # Branch

    branch_id: Optional[int] = None

    # Notes

    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    # Status

    status: Optional[VendorStatus] = None


# ============================================================
# RESPONSE
# ============================================================

class VendorResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    client_id: int

    vendor_code: str

    vendor_name: str

    vendor_type: VendorType

    status: VendorStatus

    contact_person: Optional[str] = None

    mobile: str

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

    credit_days: int

    credit_limit: Decimal

    product_categories: Optional[str] = None

    preferred_vendor: bool

    lead_time_days: int

    branch_id: Optional[int] = None

    current_outstanding: Decimal

    total_purchase_amount: Decimal

    last_purchase_date: Optional[datetime] = None

    notes: Optional[str] = None

    created_at: datetime

    updated_at: datetime