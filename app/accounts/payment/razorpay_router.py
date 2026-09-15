import json
from datetime import datetime

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
        notes=f"Razorpay payment {data.razorpay_payment_id}",
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

    await db.commit()

    return {
        "success": True,
        "message": "Razorpay webhook payment processed successfully",
        "bill_id": bill.id,
        "payment_id": payment.id,
    }