from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.accounts.bill.enum import PaymentStatus


# =========================================================
# OFFER PREVIEW
# =========================================================

class OfferPreviewRequest(BaseModel):
    bill_id: int
    offer_id: Optional[int] = None


class OfferPreviewResponse(BaseModel):
    original_amount: float
    offer_discount: float = 0.0
    final_amount: float
    due_amount: float
    message: Optional[str] = None


# =========================================================
# PRICING RESPONSE
# =========================================================

class PricingOut(BaseModel):
    id: int
    client_id: int
    branch_id: int
    item_id: int

    price: float
    cost_price: float | None = None
    discount: float | None = None
    tax: float | None = None
    calories: int | None = None

    is_active: bool
    created_at: datetime

    cgst_rate: float | None = None
    sgst_rate: float | None = None

    discounted_price: float | None = None
    cgst_amount: float | None = None
    sgst_amount: float | None = None
    total_tax_amount: float | None = None
    total_price: float | None = None

    class Config:
        from_attributes = True


# =========================================================
# ITEM RESPONSE
# =========================================================

class ItemOut(BaseModel):
    id: int
    name: str

    client_id: int
    category_id: int | None = None
    branch_id: int | None = None

    created_at: datetime
    is_active: bool

    pricings: List[PricingOut] = Field(
        default_factory=list
    )

    class Config:
        from_attributes = True


# =========================================================
# BILL RESPONSE
# =========================================================

class BillOut(BaseModel):
    id: int
    order_id: int
    branch_id: int

    invoice_no: str
    order_type: str

    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    table_id: Optional[int] = None

    payment_status: PaymentStatus
    payment_method: Optional[str] = None

    created_at: datetime

    items: List[ItemOut] = Field(
        default_factory=list
    )

    subtotal: float

    cgst_percent: float
    cgst_amount: float

    sgst_percent: float
    sgst_amount: float

    service_charge_percent: float
    service_charge_amount: float

    tax_total: float

    discount_amount: float
    round_off_amount: float

    grand_total: float

    paid_amount: float
    due_amount: float

    footer_message: str

    offer_id: Optional[int] = None
    offer_discount: float = 0.0

    final_amount: Optional[float] = None

    is_edited: bool = False

    class Config:
        from_attributes = True


# =========================================================
# BILL STATUS
# =========================================================

class BillStatusUpdate(BaseModel):
    payment_status: PaymentStatus


class BillStatusResponse(BaseModel):
    id: int
    payment_status: PaymentStatus

    paid_amount: float
    due_amount: float

    final_amount: Optional[float] = None

    is_edited: bool
    offer_discount: float = 0.0

    class Config:
        from_attributes = True


# =========================================================
# EDIT BILL
# =========================================================

class EditBillResponse(BaseModel):
    id: int
    payment_status: PaymentStatus
    is_edited: bool

    class Config:
        from_attributes = True


class BillItemUpdate(BaseModel):
    item_id: int

    # 0 means delete
    quantity: int = Field(
        ge=0
    )


class EditBillItemsRequest(BaseModel):
    items: List[BillItemUpdate]


class AddBillItemRequest(BaseModel):
    item_id: int
    quantity: int = Field(
        gt=0
    )




