from datetime import date, datetime
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# ============================================================
# INVOICE PREVIEW
# ============================================================

class PurchaseInvoicePreviewResponse(BaseModel):
    branch_id: int
    invoice_number: str
    invoice_date: date


# ============================================================
# PURCHASE ITEM CREATE
# ============================================================

class PurchaseItemCreate(BaseModel):
    inventory_item_id: Optional[int] = None

    godown_id: Optional[int] = None

    item_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    row_category: Optional[str] = "other"

    # Base unit
    unit: str = Field(
        ...,
        min_length=1,
    )

    # Purchase/display unit
    display_unit: Optional[str] = None

    conversion_factor: float = Field(
        default=1,
        gt=0,
    )

    quantity: float = Field(
        ...,
        gt=0,
    )

    reorder_level: float = Field(
        default=0,
        ge=0,
    )

    rate: float = Field(
        default=0,
        ge=0,
    )

    vendor_name: Optional[str] = None

    vendor_phone: Optional[str] = None

    discount_percent: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    tax_percent: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    amount: Optional[float] = Field(
        default=None,
        ge=0,
    )

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Item name is required")

        return value

    @field_validator(
        "unit",
        "display_unit",
        "row_category",
        "vendor_name",
        "vendor_phone",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value):
        if value is None:
            return value

        if isinstance(value, str):
            return value.strip()

        return value

    @field_validator("conversion_factor")
    @classmethod
    def validate_conversion_factor(cls, value):
        if value <= 0:
            raise ValueError(
                "Conversion factor must be greater than 0"
            )

        return value


# ============================================================
# PURCHASE ITEM UPDATE
# ============================================================

class PurchaseItemUpdate(BaseModel):
    id: Optional[int] = None

    inventory_item_id: Optional[int] = None

    godown_id: Optional[int] = None

    item_name: Optional[str] = None

    row_category: Optional[str] = None

    unit: Optional[str] = None

    display_unit: Optional[str] = None

    conversion_factor: Optional[float] = Field(
        default=None,
        gt=0,
    )

    quantity: Optional[float] = Field(
        default=None,
        gt=0,
    )

    reorder_level: Optional[float] = Field(
        default=None,
        ge=0,
    )

    rate: Optional[float] = Field(
        default=None,
        ge=0,
    )

    vendor_name: Optional[str] = None

    vendor_phone: Optional[str] = None

    discount_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    tax_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    amount: Optional[float] = Field(
        default=None,
        ge=0,
    )


# ============================================================
# PURCHASE ITEM RESPONSE
# ============================================================

class PurchaseItemResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    purchase_entry_id: Optional[int] = None

    inventory_item_id: Optional[int] = None

    godown_id: Optional[int] = None

    item_name: str

    row_category: Optional[str] = None

    unit: str

    display_unit: Optional[str] = None

    conversion_factor: float

    quantity: float

    reorder_level: float

    rate: float

    vendor_name: Optional[str] = None

    vendor_phone: Optional[str] = None

    discount_percent: float

    tax_percent: float

    amount: float

    created_at: Optional[datetime] = None


# ============================================================
# PURCHASE CREATE
# ============================================================

class PurchaseCreate(BaseModel):
    model_config = ConfigDict(
        extra="ignore"
    )

    # Backend generated
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None

    branch_id: int = Field(
        ...,
        gt=0,
    )

    supplier_id: int = Field(
        ...,
        gt=0,
    )

    supplier_invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    supplier_invoice_date: date

    delivery_date: Optional[date] = None

    reference_number: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    payment_terms: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    due_date: Optional[date] = None

    notes: Optional[str] = None

    subtotal: float = Field(
        default=0,
        ge=0,
    )

    tax_amount: float = Field(
        default=0,
        ge=0,
    )

    discount_amount: float = Field(
        default=0,
        ge=0,
    )

    grand_total: float = Field(
        default=0,
        ge=0,
    )

    items: List[PurchaseItemCreate] = Field(
        default_factory=list
    )


# ============================================================
# PURCHASE UPDATE
# ============================================================

class PurchaseUpdate(BaseModel):
    supplier_id: Optional[int] = Field(
        default=None,
        gt=0,
    )

    supplier_invoice_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    supplier_invoice_date: Optional[date] = None

    delivery_date: Optional[date] = None

    reference_number: Optional[str] = None

    payment_terms: Optional[str] = None

    due_date: Optional[date] = None

    notes: Optional[str] = None

    subtotal: Optional[float] = Field(
        default=None,
        ge=0,
    )

    tax_amount: Optional[float] = Field(
        default=None,
        ge=0,
    )

    discount_amount: Optional[float] = Field(
        default=None,
        ge=0,
    )

    grand_total: Optional[float] = Field(
        default=None,
        ge=0,
    )

    items: Optional[List[PurchaseItemCreate]] = None


# ============================================================
# PURCHASE RESPONSE
# ============================================================

class PurchaseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    branch_id: int

    supplier_id: int

    invoice_number: str

    invoice_date: date

    supplier_invoice_number: str

    supplier_invoice_date: date

    delivery_date: Optional[date] = None

    reference_number: Optional[str] = None

    payment_terms: Optional[str] = None

    due_date: Optional[date] = None

    notes: Optional[str] = None

    subtotal: float

    tax_amount: float

    discount_amount: float

    grand_total: float

    created_at: datetime

    updated_at: datetime

    items: List[PurchaseItemResponse] = Field(
        default_factory=list
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

PurchaseEntryCreate = PurchaseCreate
PurchaseEntryResponse = PurchaseResponse