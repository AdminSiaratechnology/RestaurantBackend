import os
from typing import Any

import razorpay

from fastapi import HTTPException


# ============================================================
# CONFIG
# ============================================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


if not RAZORPAY_KEY_ID:
    raise RuntimeError(
        "RAZORPAY_KEY_ID is not configured"
    )

if not RAZORPAY_KEY_SECRET:
    raise RuntimeError(
        "RAZORPAY_KEY_SECRET is not configured"
    )


# ============================================================
# CLIENT
# ============================================================

razorpay_client = razorpay.Client(
    auth=(
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET,
    )
)


# ============================================================
# MONEY
# ============================================================


def rupees_to_paise(
    amount: float,
) -> int:

    amount = round(
        float(amount or 0),
        2,
    )

    if amount < 0:
        amount = 0.0

    return int(
        round(
            amount * 100
        )
    )


def paise_to_rupees(
    amount: int | float,
) -> float:

    return round(
        float(amount or 0) / 100,
        2,
    )


# ============================================================
# CREATE ORDER
# ============================================================


def create_razorpay_order(
    *,
    amount: float,
    bill_id: int,
    invoice_no: str | None = None,
) -> dict[str, Any]:

    amount_paise = rupees_to_paise(
        amount
    )

    if amount_paise <= 0:

        raise HTTPException(
            status_code=400,
            detail="Razorpay amount must be greater than zero",
        )

    notes = {
        "bill_id": str(bill_id),
    }

    if invoice_no:
        notes["invoice_no"] = str(
            invoice_no
        )

    try:

        order = razorpay_client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"bill_{bill_id}",
                "notes": notes,
            }
        )

        return order

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to create Razorpay order: "
                f"{str(exc)}"
            ),
        )


# ============================================================
# VERIFY CHECKOUT PAYMENT
# ============================================================


def verify_razorpay_payment(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> None:

    if not razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Razorpay order ID is required",
        )

    if not razorpay_payment_id:
        raise HTTPException(
            status_code=400,
            detail="Razorpay payment ID is required",
        )

    if not razorpay_signature:
        raise HTTPException(
            status_code=400,
            detail="Razorpay signature is required",
        )

    try:

        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": (
                    razorpay_order_id
                ),
                "razorpay_payment_id": (
                    razorpay_payment_id
                ),
                "razorpay_signature": (
                    razorpay_signature
                ),
            }
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay payment signature",
        )


# ============================================================
# FETCH PAYMENT
# ============================================================


def fetch_razorpay_payment(
    payment_id: str,
) -> dict[str, Any]:

    try:

        return razorpay_client.payment.fetch(
            payment_id
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to fetch Razorpay payment: "
                f"{str(exc)}"
            ),
        )


# ============================================================
# WEBHOOK VERIFY
# ============================================================


def verify_razorpay_webhook(
    *,
    body: bytes,
    signature: str | None,
) -> None:

    if not RAZORPAY_WEBHOOK_SECRET:

        raise HTTPException(
            status_code=500,
            detail=(
                "RAZORPAY_WEBHOOK_SECRET "
                "is not configured"
            ),
        )

    if not signature:

        raise HTTPException(
            status_code=400,
            detail="Missing Razorpay webhook signature",
        )

    try:

        razorpay_client.utility.verify_webhook_signature(
            body.decode("utf-8"),
            signature,
            RAZORPAY_WEBHOOK_SECRET,
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay webhook signature",
        )