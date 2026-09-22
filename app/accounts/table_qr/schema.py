from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TableQROut(BaseModel):
    id: int
    branch_id: int
    table_id: int
    qr_token: str | None = None
    qr_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerInfo(BaseModel):
    id: int
    name: str
    phone: str | None = None
    email: str | None = None


class QRResolutionOut(BaseModel):
    session_token: str
    branch_name: str
    table_name: str
    floor: str | None = None
    number_of_seats: int
    currency: str
    tax_type: str
    decimal_places: int
    customer: CustomerInfo | None = None


class SessionCustomerAttachReq(BaseModel):
    name: str = Field(..., min_length=1, description="Customer name")
    phone: str | None = Field(None, description="Customer phone number")
    email: str | None = Field(None, description="Customer email address")


class SessionCustomerOut(BaseModel):
    session_token: str
    customer_id: int
    name: str
    phone: str | None = None
    email: str | None = None


class PublicOrderItemReq(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class PublicOrderCreateReq(BaseModel):
    items: list[PublicOrderItemReq] = Field(..., min_items=1)
    notes: str | None = None


class PublicOrderOut(BaseModel):
    id: int
    table_id: int
    order_type: str
    source: str
    status: str
    total_amount: float
    created_at: datetime
    items: list[dict]


class RazorpayInitiateOut(BaseModel):
    order_id: int
    bill_id: int
    invoice_no: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount: float
    amount_paise: int
    currency: str


class RazorpayPaymentVerifyReq(BaseModel):
    bill_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentVerifyOut(BaseModel):
    status: str
    message: str
    bill_id: int
    order_id: int
    payment_id: int
    order_status: str


class PublicPaymentFailureReq(BaseModel):
    bill_id: int
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    error_code: str | None = None
    error_description: str | None = None
    error_source: str | None = None
    error_step: str | None = None
    error_reason: str | None = None

