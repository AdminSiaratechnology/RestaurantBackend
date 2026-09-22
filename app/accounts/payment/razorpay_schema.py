from typing import Any, Optional
from pydantic import BaseModel, Field


# ============================================================
# CREATE RAZORPAY ORDER
# ============================================================


class RazorpayCreateRequest(BaseModel):

    bill_id: int

    offer_id: Optional[int] = None

    use_wallet: bool = False


# ============================================================
# CREATE ORDER RESPONSE
# ============================================================


class RazorpayCreateResponse(BaseModel):

    bill_id: int

    razorpay_order_id: str

    razorpay_key_id: str

    amount: int

    amount_rupees: float

    currency: str

    invoice_no: Optional[str] = None


# ============================================================
# VERIFY PAYMENT
# ============================================================


class RazorpayVerifyRequest(BaseModel):

    bill_id: int

    razorpay_order_id: str = Field(
        min_length=1,
    )

    razorpay_payment_id: str = Field(
        min_length=1,
    )

    razorpay_signature: str = Field(
        min_length=1,
    )


# ============================================================
# VERIFY RESPONSE
# ============================================================


class RazorpayVerifyResponse(BaseModel):

    success: bool

    bill_id: int

    payment_id: int

    razorpay_payment_id: str

    message: str

    payment_status: Optional[str] = "complete"

    bill_status: Optional[str] = "complete"

    payment_method: Optional[str] = "razorpay"


# ============================================================
# RECORD PAYMENT FAILURE
# ============================================================


class RazorpayFailureRequest(BaseModel):

    bill_id: int

    razorpay_order_id: Optional[str] = None

    razorpay_payment_id: Optional[str] = None

    error_code: Optional[str] = None

    error_description: Optional[str] = None

    error_source: Optional[str] = None

    error_step: Optional[str] = None

    error_reason: Optional[str] = None

    error_metadata: Optional[dict[str, Any]] = None


class RazorpayFailureResponse(BaseModel):

    success: bool

    bill_id: int

    message: str

    failure_recorded: bool = True


# ============================================================
# TRANSACTION DETAILS & LIFECYCLE AUDIT RESPONSE
# ============================================================


class LifecycleEvent(BaseModel):

    title: str

    description: str

    timestamp: Optional[str] = None

    status: str  # "completed", "failed", "pending", "info"

    event_type: str


class RazorpayTransactionDetailsResponse(BaseModel):

    bill_id: int

    order_id: int

    invoice_no: Optional[str] = None

    branch_id: Optional[int] = None

    customer_name: Optional[str] = None

    customer_phone: Optional[str] = None

    payment_status: str

    payment_method: Optional[str] = None

    subtotal: float = 0.0

    tax_total: float = 0.0

    discount_amount: float = 0.0

    offer_discount: float = 0.0

    wallet_discount: float = 0.0

    grand_total: float = 0.0

    final_amount: float = 0.0

    paid_amount: float = 0.0

    due_amount: float = 0.0

    razorpay_order_id: Optional[str] = None

    razorpay_payment_id: Optional[str] = None

    razorpay_signature: Optional[str] = None

    payment_verified_at: Optional[str] = None

    billed_at: Optional[str] = None

    razorpay_payment_details: Optional[dict[str, Any]] = None

    failure_details: Optional[dict[str, Any]] = None

    lifecycle_events: list[LifecycleEvent] = []