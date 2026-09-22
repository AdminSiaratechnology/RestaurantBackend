import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
)

from sqlalchemy import select

from app.db.config import SessionDep

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.payment.model import Payment
from app.accounts.payment.schema import PaymentCreate
from app.accounts.payment.enum import PaymentMethod

from app.accounts.payment.service import (
    make_payment_service,
    resolve_bill_customer,
    get_offer_or_404,
)

from app.accounts.offer.helper import (
    validate_and_calculate_offer,
    calculate_final_amount,
)

from app.accounts.crm.wallet.service import (
    calculate_wallet_discount,
)

from app.accounts.payment.razorpay_schema import (
    RazorpayCreateRequest,
    RazorpayCreateResponse,
    RazorpayVerifyRequest,
    RazorpayVerifyResponse,
    RazorpayFailureRequest,
    RazorpayFailureResponse,
    RazorpayTransactionDetailsResponse,
    LifecycleEvent,
)

from app.accounts.payment.razorpay_service import (
    RAZORPAY_KEY_ID,
    create_razorpay_order,
    fetch_razorpay_payment,
    verify_razorpay_payment,
    verify_razorpay_webhook,
    paise_to_rupees,
    rupees_to_paise,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/razorpay",
    tags=["Razorpay Payment"],
)


# ============================================================
# CREATE RAZORPAY ORDER
# ============================================================


@router.post(
    "/create",
    response_model=RazorpayCreateResponse,
)
async def create_payment_order(
    data: RazorpayCreateRequest,
    db: SessionDep,
):
    # --------------------------------------------------------
    # GET BILL + LOCK
    # --------------------------------------------------------

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == data.bill_id
        )
        .with_for_update()
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    # --------------------------------------------------------
    # ALREADY PAID
    # --------------------------------------------------------

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Bill is already paid",
        )

    # --------------------------------------------------------
    # ORIGINAL AMOUNT
    # --------------------------------------------------------

    base_subtotal = float(bill.subtotal or 0)
    base_tax = float(bill.tax_total or 0)
    base_service_charge = float(bill.service_charge_amount or 0)
    base_discount = float(bill.discount_amount or 0)
    calculated_grand = base_subtotal + base_tax + base_service_charge - base_discount

    original_amount = round(
        float(
            bill.grand_total
            if (bill.grand_total is not None and bill.grand_total > 0)
            else max(0.0, calculated_grand)
        ),
        2,
    )

    if original_amount < 0:
        original_amount = 0.0

    # --------------------------------------------------------
    # CUSTOMER
    # --------------------------------------------------------

    customer_id = await resolve_bill_customer(
        db,
        bill,
    )

    # --------------------------------------------------------
    # OFFER
    # --------------------------------------------------------

    offer_discount = 0.0
    applied_offer_id = None

    target_offer_id = data.offer_id or bill.offer_id

    if target_offer_id:
        offer = await get_offer_or_404(
            db,
            target_offer_id,
        )

        offer_discount = round(
            float(
                validate_and_calculate_offer(
                    offer,
                    original_amount,
                )
                or 0
            ),
            2,
        )
        applied_offer_id = offer.id

        amount_after_offer = round(
            calculate_final_amount(
                original_amount,
                offer_discount,
            ),
            2,
        )
    else:
        amount_after_offer = original_amount

    if amount_after_offer < 0:
        amount_after_offer = 0.0

    # --------------------------------------------------------
    # WALLET (CALCULATE WITHOUT DEBITING)
    # --------------------------------------------------------

    wallet_discount = 0.0

    if data.use_wallet:
        if not customer_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "CRM customer is required "
                    "to use wallet."
                ),
            )

        wallet_info = await calculate_wallet_discount(
            db=db,
            customer_id=customer_id,
            client_id=bill.client_id,
            branch_id=bill.branch_id,
            amount=amount_after_offer,
            lock_wallet=False,
        )

        wallet_discount = round(
            float(
                wallet_info.get(
                    "wallet_discount",
                    0.0,
                )
                or 0
            ),
            2,
        )

        if wallet_discount < 0:
            wallet_discount = 0.0

        if wallet_discount > amount_after_offer:
            wallet_discount = amount_after_offer

    # --------------------------------------------------------
    # FINAL AMOUNT
    # --------------------------------------------------------

    final_amount = round(
        amount_after_offer - wallet_discount,
        2,
    )

    if final_amount < 0:
        final_amount = 0.0

    # --------------------------------------------------------
    # REJECT IF FINAL AMOUNT <= 0
    # --------------------------------------------------------

    if final_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Razorpay cannot be used when "
                "the final payable amount is zero or negative. "
                "Complete the bill using wallet/discount."
            ),
        )

    # --------------------------------------------------------
    # CREATE RAZORPAY ORDER
    # --------------------------------------------------------

    razorpay_order = create_razorpay_order(
        amount=final_amount,
        bill_id=bill.id,
        invoice_no=bill.invoice_no,
    )

    # --------------------------------------------------------
    # STORE ORDER ID & PRICING SNAPSHOT ON BILL
    # --------------------------------------------------------

    bill.razorpay_order_id = razorpay_order["id"]
    bill.razorpay_order_amount = final_amount
    bill.razorpay_offer_id = applied_offer_id
    bill.razorpay_wallet_discount = wallet_discount
    # Clear previous error state on new attempt
    bill.razorpay_error_code = None
    bill.razorpay_error_description = None
    bill.razorpay_error_reason = None
    bill.razorpay_error_source = None
    bill.razorpay_error_step = None
    bill.razorpay_error_at = None

    await db.commit()

    return RazorpayCreateResponse(
        bill_id=bill.id,
        razorpay_order_id=razorpay_order["id"],
        razorpay_key_id=RAZORPAY_KEY_ID,
        amount=int(razorpay_order["amount"]),
        amount_rupees=paise_to_rupees(razorpay_order["amount"]),
        currency=razorpay_order["currency"],
        invoice_no=bill.invoice_no,
    )


# ============================================================
# VERIFY RAZORPAY PAYMENT
# ============================================================


@router.post(
    "/verify",
    response_model=RazorpayVerifyResponse,
)
async def verify_payment(
    data: RazorpayVerifyRequest,
    db: SessionDep,
):
    # --------------------------------------------------------
    # GET BILL + LOCK
    # --------------------------------------------------------

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == data.bill_id
        )
        .with_for_update()
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    # --------------------------------------------------------
    # IDEMPOTENCY: ALREADY COMPLETED
    # --------------------------------------------------------

    if bill.payment_status == PaymentStatus.complete:
        existing_payment_result = await db.execute(
            select(Payment)
            .where(
                Payment.bill_id == bill.id
            )
            .order_by(
                Payment.id.desc()
            )
        )

        existing_payment = (
            existing_payment_result
            .scalars()
            .first()
        )

        if existing_payment:
            return RazorpayVerifyResponse(
                success=True,
                bill_id=bill.id,
                payment_id=existing_payment.id,
                razorpay_payment_id=(
                    bill.razorpay_payment_id
                    or data.razorpay_payment_id
                ),
                payment_status="complete",
                bill_status="complete",
                payment_method="razorpay",
                message="Payment was already completed",
            )

        raise HTTPException(
            status_code=400,
            detail="Bill is already paid",
        )

    # --------------------------------------------------------
    # VERIFY ORDER BELONGS TO THIS BILL
    # --------------------------------------------------------

    if not bill.razorpay_order_id or bill.razorpay_order_id != data.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Razorpay order does not belong to this bill",
        )

    # --------------------------------------------------------
    # CHECK PAYMENT ID NOT USED ON ANOTHER BILL
    # --------------------------------------------------------

    payment_result = await db.execute(
        select(Bill)
        .where(
            Bill.razorpay_payment_id == data.razorpay_payment_id
        )
    )

    payment_bill = payment_result.scalar_one_or_none()

    if payment_bill and payment_bill.id != bill.id:
        raise HTTPException(
            status_code=409,
            detail="Razorpay payment has already been used for another bill",
        )

    # --------------------------------------------------------
    # VERIFY CHECKOUT SIGNATURE SERVER-SIDE
    # --------------------------------------------------------

    verify_razorpay_payment(
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
    )

    # --------------------------------------------------------
    # FETCH PAYMENT FROM RAZORPAY API
    # --------------------------------------------------------

    razorpay_payment = fetch_razorpay_payment(data.razorpay_payment_id)

    payment_status = str(razorpay_payment.get("status", "")).lower()

    if payment_status != "captured":
        raise HTTPException(
            status_code=400,
            detail="Razorpay payment is not captured",
        )

    # --------------------------------------------------------
    # VERIFY FETCHED ORDER ID MATCHES STORED ORDER ID
    # --------------------------------------------------------

    fetched_order_id = razorpay_payment.get("order_id")

    if fetched_order_id != bill.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Razorpay payment does not belong to this order",
        )

    # --------------------------------------------------------
    # VERIFY EXACT AMOUNT MATCHES STORED SNAPSHOT
    # --------------------------------------------------------

    razorpay_amount_paise = int(razorpay_payment.get("amount", 0))

    expected_amount_rupees = (
        bill.razorpay_order_amount
        if bill.razorpay_order_amount is not None
        else bill.final_amount
    )
    expected_paise = rupees_to_paise(expected_amount_rupees)

    if razorpay_amount_paise != expected_paise:
        raise HTTPException(
            status_code=400,
            detail="Razorpay payment amount does not match order amount",
        )

    # --------------------------------------------------------
    # COMPLETE THROUGH EXISTING make_payment_service()
    # --------------------------------------------------------

    verified_payment_amount = paise_to_rupees(razorpay_amount_paise)

    # Build rich notes with payment sub-method if available
    method_name = razorpay_payment.get("method", "razorpay")
    method_detail = ""
    if method_name == "upi" and razorpay_payment.get("vpa"):
        method_detail = f" (UPI: {razorpay_payment.get('vpa')})"
    elif method_name == "card" and razorpay_payment.get("card"):
        card_info = razorpay_payment.get("card", {})
        method_detail = f" ({card_info.get('network', '')} Card **** {card_info.get('last4', '')})"
    elif method_name == "netbanking" and razorpay_payment.get("bank"):
        method_detail = f" (NetBanking: {razorpay_payment.get('bank')})"

    payment_data = PaymentCreate(
        bill_id=bill.id,
        payments=[
            {
                "payment_method": PaymentMethod.razorpay,
                "payment_amount": verified_payment_amount,
            }
        ],
        payment_reference=data.razorpay_payment_id,
        offer_id=bill.razorpay_offer_id,
        use_wallet=bool(bill.razorpay_wallet_discount and bill.razorpay_wallet_discount > 0),
        notes=f"Razorpay payment {data.razorpay_payment_id}{method_detail}",
    )

    payment = await make_payment_service(
        db,
        payment_data,
        razorpay_verified=True,
        wallet_discount_override=bill.razorpay_wallet_discount,
    )

    # --------------------------------------------------------
    # PERSIST RAZORPAY DETAILS ON BILL
    # --------------------------------------------------------

    bill_result = await db.execute(
        select(Bill)
        .where(
            Bill.id == bill.id
        )
        .with_for_update()
    )

    updated_bill = bill_result.scalar_one()

    updated_bill.razorpay_order_id = data.razorpay_order_id
    updated_bill.razorpay_payment_id = data.razorpay_payment_id
    updated_bill.razorpay_signature = data.razorpay_signature
    updated_bill.payment_verified_at = datetime.utcnow()
    updated_bill.payment_method = "razorpay"
    # Clear any past failure status
    updated_bill.razorpay_error_code = None
    updated_bill.razorpay_error_description = None
    updated_bill.razorpay_error_reason = None
    updated_bill.razorpay_error_source = None
    updated_bill.razorpay_error_step = None
    updated_bill.razorpay_error_at = None

    await db.commit()

    return RazorpayVerifyResponse(
        success=True,
        bill_id=updated_bill.id,
        payment_id=payment.id,
        razorpay_payment_id=data.razorpay_payment_id,
        payment_status="complete",
        bill_status="complete",
        payment_method="razorpay",
        message="Razorpay payment verified and bill completed successfully",
    )


# ============================================================
# RECORD PAYMENT FAILURE / DISMISSAL
# ============================================================


@router.post(
    "/failure",
    response_model=RazorpayFailureResponse,
)
async def record_payment_failure(
    data: RazorpayFailureRequest,
    db: SessionDep,
):
    result = await db.execute(
        select(Bill)
        .where(Bill.id == data.bill_id)
        .with_for_update()
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    # Do not overwrite completed payments
    if bill.payment_status == PaymentStatus.complete:
        return RazorpayFailureResponse(
            success=True,
            bill_id=bill.id,
            message="Bill already completed; failure not recorded",
            failure_recorded=False,
        )

    bill.razorpay_error_code = data.error_code or "PAYMENT_FAILED"
    bill.razorpay_error_description = (
        data.error_description or "Payment was declined, cancelled, or failed during checkout."
    )
    bill.razorpay_error_source = data.error_source
    bill.razorpay_error_step = data.error_step
    bill.razorpay_error_reason = data.error_reason
    bill.razorpay_error_at = datetime.utcnow()

    if data.razorpay_payment_id:
        bill.razorpay_payment_id = data.razorpay_payment_id

    await db.commit()

    return RazorpayFailureResponse(
        success=True,
        bill_id=bill.id,
        message="Payment failure recorded successfully",
        failure_recorded=True,
    )


# ============================================================
# TRANSACTION DETAILS & LIFECYCLE AUDIT TRAIL
# ============================================================


@router.get(
    "/details/{bill_id}",
    response_model=RazorpayTransactionDetailsResponse,
)
async def get_transaction_details(
    bill_id: int,
    db: SessionDep,
):
    result = await db.execute(
        select(Bill).where(Bill.id == bill_id)
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    # Build live razorpay metadata if razorpay_payment_id exists
    razorpay_details: Optional[dict[str, Any]] = None
    if bill.razorpay_payment_id:
        try:
            raw_payment = fetch_razorpay_payment(bill.razorpay_payment_id)
            razorpay_details = {
                "id": raw_payment.get("id"),
                "status": raw_payment.get("status"),
                "method": raw_payment.get("method"),
                "amount": paise_to_rupees(raw_payment.get("amount", 0)),
                "currency": raw_payment.get("currency", "INR"),
                "fee": paise_to_rupees(raw_payment.get("fee", 0)) if raw_payment.get("fee") is not None else None,
                "tax": paise_to_rupees(raw_payment.get("tax", 0)) if raw_payment.get("tax") is not None else None,
                "vpa": raw_payment.get("vpa"),
                "bank": raw_payment.get("bank"),
                "wallet": raw_payment.get("wallet"),
                "card": raw_payment.get("card"),
                "email": raw_payment.get("email"),
                "contact": raw_payment.get("contact"),
                "acquirer_data": raw_payment.get("acquirer_data"),
                "created_at": (
                    datetime.fromtimestamp(raw_payment.get("created_at")).isoformat()
                    if raw_payment.get("created_at")
                    else None
                ),
            }
        except Exception as e:
            logger.warning(f"Could not fetch live Razorpay payment details for {bill.razorpay_payment_id}: {e}")

    # Build failure details dictionary
    failure_details: Optional[dict[str, Any]] = None
    if bill.razorpay_error_code or bill.razorpay_error_description:
        failure_details = {
            "error_code": bill.razorpay_error_code,
            "error_description": bill.razorpay_error_description,
            "error_source": bill.razorpay_error_source,
            "error_step": bill.razorpay_error_step,
            "error_reason": bill.razorpay_error_reason,
            "error_at": bill.razorpay_error_at.isoformat() if bill.razorpay_error_at else None,
        }

    # Build chronological lifecycle timeline
    events: list[LifecycleEvent] = []

    # Step 1: Bill Generation
    events.append(
        LifecycleEvent(
            title="Bill Generated",
            description=f"Invoice #{bill.invoice_no} created with grand total ₹{float(bill.grand_total or 0):.2f}",
            timestamp=bill.billed_at.isoformat() if bill.billed_at else (bill.created_at.isoformat() if bill.created_at else None),
            status="completed",
            event_type="bill_created",
        )
    )

    # Step 2: Razorpay Order Creation
    if bill.razorpay_order_id:
        events.append(
            LifecycleEvent(
                title="Razorpay Order Initialized",
                description=f"Order {bill.razorpay_order_id} created for ₹{float(bill.razorpay_order_amount or bill.final_amount or 0):.2f}",
                timestamp=bill.billed_at.isoformat() if bill.billed_at else None,
                status="completed",
                event_type="order_created",
            )
        )

    # Step 3: Payment Verification or Failure
    if bill.payment_status == PaymentStatus.complete and bill.razorpay_payment_id:
        events.append(
            LifecycleEvent(
                title="Payment Authorized & Captured",
                description=f"Payment ID {bill.razorpay_payment_id} captured via {bill.payment_method or 'razorpay'}",
                timestamp=bill.payment_verified_at.isoformat() if bill.payment_verified_at else None,
                status="completed",
                event_type="payment_success",
            )
        )
        events.append(
            LifecycleEvent(
                title="Cryptographic Signature Verified",
                description="HMAC SHA-256 signature verified by server",
                timestamp=bill.payment_verified_at.isoformat() if bill.payment_verified_at else None,
                status="completed",
                event_type="signature_verified",
            )
        )
        events.append(
            LifecycleEvent(
                title="Bill Settled & Table Released",
                description=f"Bill marked as PAID. Total settled: ₹{float(bill.paid_amount or bill.final_amount or 0):.2f}",
                timestamp=bill.payment_verified_at.isoformat() if bill.payment_verified_at else None,
                status="completed",
                event_type="bill_settled",
            )
        )
    elif bill.razorpay_error_code or bill.razorpay_error_description:
        events.append(
            LifecycleEvent(
                title=f"Payment Failed ({bill.razorpay_error_reason or bill.razorpay_error_code})",
                description=bill.razorpay_error_description or "Payment was declined or cancelled during checkout",
                timestamp=bill.razorpay_error_at.isoformat() if bill.razorpay_error_at else None,
                status="failed",
                event_type="payment_failed",
            )
        )
    elif bill.razorpay_order_id:
        events.append(
            LifecycleEvent(
                title="Awaiting Customer Payment",
                description="Razorpay checkout active, awaiting user payment completion",
                timestamp=None,
                status="pending",
                event_type="payment_pending",
            )
        )

    return RazorpayTransactionDetailsResponse(
        bill_id=bill.id,
        order_id=bill.order_id,
        invoice_no=bill.invoice_no,
        branch_id=bill.branch_id,
        customer_name=bill.customer_name,
        customer_phone=bill.customer_phone,
        payment_status=bill.payment_status.value if hasattr(bill.payment_status, "value") else str(bill.payment_status),
        payment_method=bill.payment_method,
        subtotal=float(bill.subtotal or 0),
        tax_total=float(bill.tax_total or 0),
        discount_amount=float(bill.discount_amount or 0),
        offer_discount=float(bill.offer_discount or 0),
        wallet_discount=float(bill.wallet_discount or 0),
        grand_total=float(bill.grand_total or 0),
        final_amount=float(bill.final_amount or 0),
        paid_amount=float(bill.paid_amount or 0),
        due_amount=float(bill.due_amount or 0),
        razorpay_order_id=bill.razorpay_order_id,
        razorpay_payment_id=bill.razorpay_payment_id,
        razorpay_signature=bill.razorpay_signature,
        payment_verified_at=bill.payment_verified_at.isoformat() if bill.payment_verified_at else None,
        billed_at=bill.billed_at.isoformat() if bill.billed_at else None,
        razorpay_payment_details=razorpay_details,
        failure_details=failure_details,
        lifecycle_events=events,
    )


@router.get(
    "/order/{order_id}",
    response_model=RazorpayTransactionDetailsResponse,
)
async def get_transaction_details_by_order(
    order_id: int,
    db: SessionDep,
):
    result = await db.execute(
        select(Bill).where(Bill.order_id == order_id)
    )
    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="No bill found for this order",
        )

    return await get_transaction_details(bill.id, db)


# ============================================================
# WEBHOOK
# ============================================================


@router.post(
    "/webhook",
)
async def razorpay_webhook(
    request: Request,
    db: SessionDep,
    x_razorpay_signature: str | None = Header(
        default=None,
        alias="X-Razorpay-Signature",
    ),
):
    # --------------------------------------------------------
    # RAW BODY & SIGNATURE VERIFICATION
    # --------------------------------------------------------

    body = await request.body()

    verify_razorpay_webhook(
        body=body,
        signature=x_razorpay_signature,
    )

    # --------------------------------------------------------
    # PARSE PAYLOAD
    # --------------------------------------------------------

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook JSON",
        )

    event = payload.get("event")

    # --------------------------------------------------------
    # HANDLE PAYMENT FAILURE WEBHOOK
    # --------------------------------------------------------
    if event == "payment.failed":
        payment_entity = (
            payload.get("payload", {}).get("payment", {}).get("entity", {})
        )
        razorpay_order_id = payment_entity.get("order_id")

        if razorpay_order_id:
            result = await db.execute(
                select(Bill)
                .where(Bill.razorpay_order_id == razorpay_order_id)
                .with_for_update()
            )
            bill = result.scalar_one_or_none()

            if bill and bill.payment_status != PaymentStatus.complete:
                bill.razorpay_error_code = (
                    payment_entity.get("error_code") or "GATEWAY_PAYMENT_FAILED"
                )
                bill.razorpay_error_description = payment_entity.get(
                    "error_description"
                ) or "Razorpay webhook reported payment failure"
                bill.razorpay_error_source = payment_entity.get("error_source")
                bill.razorpay_error_step = payment_entity.get("error_step")
                bill.razorpay_error_reason = payment_entity.get("error_reason")
                bill.razorpay_error_at = datetime.utcnow()
                if payment_entity.get("id"):
                    bill.razorpay_payment_id = payment_entity.get("id")

                await db.commit()

        return {
            "success": True,
            "message": "Payment failure event recorded successfully",
        }

    if event not in {
        "payment.captured",
        "order.paid",
    }:
        return {
            "success": True,
            "message": "Event ignored",
        }

    # --------------------------------------------------------
    # EXTRACT PAYMENT & ORDER ENTITIES
    # --------------------------------------------------------

    payment_entity = (
        payload.get("payload", {}).get("payment", {}).get("entity", {})
    )
    order_entity = (
        payload.get("payload", {}).get("order", {}).get("entity", {})
    )

    razorpay_payment_id = payment_entity.get("id")
    razorpay_order_id = payment_entity.get("order_id") or order_entity.get("id")

    if not razorpay_payment_id or not razorpay_order_id:
        return {
            "success": True,
            "message": "Missing payment ID or order ID in webhook payload",
        }

    # --------------------------------------------------------
    # FIND BILL + ROW LOCK
    # --------------------------------------------------------

    result = await db.execute(
        select(Bill)
        .where(
            Bill.razorpay_order_id == razorpay_order_id
        )
        .with_for_update()
    )

    bill = result.scalar_one_or_none()

    if not bill:
        return {
            "success": True,
            "message": "Bill not found",
        }

    # --------------------------------------------------------
    # IDEMPOTENCY CHECK
    # --------------------------------------------------------

    if bill.payment_status == PaymentStatus.complete:
        return {
            "success": True,
            "message": "Bill already completed",
        }

    # --------------------------------------------------------
    # INDEPENDENTLY FETCH & VERIFY PAYMENT FROM RAZORPAY
    # --------------------------------------------------------

    razorpay_payment = fetch_razorpay_payment(razorpay_payment_id)

    if str(razorpay_payment.get("status", "")).lower() != "captured":
        return {
            "success": True,
            "message": "Payment not captured",
        }

    fetched_order_id = razorpay_payment.get("order_id")
    if fetched_order_id != bill.razorpay_order_id:
        return {
            "success": True,
            "message": "Order ID mismatch",
        }

    razorpay_amount_paise = int(razorpay_payment.get("amount", 0))
    expected_amount_rupees = (
        bill.razorpay_order_amount
        if bill.razorpay_order_amount is not None
        else bill.final_amount
    )
    expected_paise = rupees_to_paise(expected_amount_rupees)

    if razorpay_amount_paise != expected_paise:
        return {
            "success": True,
            "message": "Amount mismatch",
        }

    # --------------------------------------------------------
    # RECONCILE VIA make_payment_service()
    # --------------------------------------------------------

    verified_payment_amount = paise_to_rupees(razorpay_amount_paise)

    payment_data = PaymentCreate(
        bill_id=bill.id,
        payments=[
            {
                "payment_method": PaymentMethod.razorpay,
                "payment_amount": verified_payment_amount,
            }
        ],
        payment_reference=razorpay_payment_id,
        offer_id=bill.razorpay_offer_id,
        use_wallet=bool(bill.razorpay_wallet_discount and bill.razorpay_wallet_discount > 0),
        notes=f"Razorpay webhook payment {razorpay_payment_id}",
    )

    payment = await make_payment_service(
        db,
        payment_data,
        razorpay_verified=True,
        wallet_discount_override=bill.razorpay_wallet_discount,
    )

    bill.razorpay_payment_id = razorpay_payment_id
    bill.payment_verified_at = datetime.utcnow()
    bill.payment_method = "razorpay"
    bill.razorpay_error_code = None
    bill.razorpay_error_description = None
    bill.razorpay_error_reason = None
    bill.razorpay_error_source = None
    bill.razorpay_error_step = None
    bill.razorpay_error_at = None

    await db.commit()

    return {
        "success": True,
        "message": "Razorpay webhook payment processed successfully",
        "bill_id": bill.id,
        "payment_id": payment.id,
    }