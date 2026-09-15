from typing import Optional

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