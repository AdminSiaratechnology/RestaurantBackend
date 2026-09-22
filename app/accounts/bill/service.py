import asyncio
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional
import secrets
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounts.bill.enum import PaymentStatus
from app.accounts.bill.invoice_template import InvoiceTemplate
from app.accounts.bill.model import Bill
from app.accounts.branch.model import Branch
from app.accounts.crm.customer_history.checkout_service import handle_customer_and_visit
from app.accounts.crm.loyalty.service import calculate_customer_rank
from app.accounts.customer.model import Customer
from app.accounts.offer.model import OfferType
from app.accounts.order.model import Order, OrderItem
from app.accounts.table.enum import TableStatus
from app.accounts.table.model import Table
from app.accounts.table_qr.model import RestaurantSession, SessionStatus
from app.accounts.tax.model import TaxBillingSetting
from app.core.cache import Cache
from app.core.tax import (
    calculate_tax_amounts,
    get_tax_type_from_country,
    resolve_branch_tax_type,
    round_money,
)

logger = logging.getLogger(__name__)


def _money(value) -> float:
    return round(float(value or 0), 2)


def _calculate_offer_discount(offer, amount: float) -> float:
    if not offer:
        return 0.0

    if not offer.is_active:
        return 0.0

    if offer.min_order_amount and amount < float(offer.min_order_amount):
        return 0.0

    if offer.offer_type == OfferType.FLAT_DISCOUNT:
        return round(min(float(offer.discount_value or 0), amount), 2)

    if offer.offer_type == OfferType.PERCENTAGE_OFF:
        return round(amount * (float(offer.discount_value or 0) / 100), 2)

    return 0.0


def _calculate_bill_totals(
    *,
    subtotal: float,
    tax_total: float,
    service_charge_percent: float,
    discount_amount: float,
    offer_discount: float,
    round_off_enabled: bool,
):
    subtotal = _money(subtotal)
    tax_total = _money(tax_total)
    discount_amount = _money(discount_amount)
    offer_discount = _money(offer_discount)

    service_charge_amount = _money(subtotal * (service_charge_percent / 100))

    before_rounding = _money(subtotal + tax_total + service_charge_amount - discount_amount)

    if round_off_enabled:
        rounded_total = float(round(before_rounding))
        round_off_amount = _money(rounded_total - before_rounding)
        grand_total = rounded_total
    else:
        round_off_amount = 0.0
        grand_total = before_rounding

    final_amount = _money(max(grand_total - offer_discount, 0))

    return {
        "subtotal": subtotal,
        "tax_total": tax_total,
        "service_charge_percent": service_charge_percent,
        "service_charge_amount": service_charge_amount,
        "discount_amount": discount_amount,
        "offer_discount": offer_discount,
        "round_off_amount": round_off_amount,
        "grand_total": grand_total,
        "final_amount": final_amount,
    }


async def get_or_create_bill_for_order(
    db: AsyncSession,
    order_id: int,
) -> Bill:
    """
    Get existing Bill or create a new one using standard DINE-IN branch tax rules.
    """
    order_res = await db.execute(
        select(Order)
        .options(selectinload(Order.order_items).selectinload(OrderItem.item))
        .where(Order.id == order_id)
    )
    order = order_res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    branch = await db.get(Branch, order.branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    decimal_places = int(getattr(branch, "decimal_places", None) or 2)

    tax_res = await db.execute(
        select(TaxBillingSetting).where(TaxBillingSetting.branch_id == order.branch_id)
    )
    tax = tax_res.scalar_one_or_none()

    effective_branch_tax_type = await resolve_branch_tax_type(db, order.branch_id)
    effective_branch_tax_type = str(effective_branch_tax_type or "GST").strip().upper()
    if effective_branch_tax_type not in {"GST", "VAT"}:
        effective_branch_tax_type = "GST"

    if not tax:
        branch_tt = getattr(branch, "tax_type", None) or get_tax_type_from_country(getattr(branch, "country", None))
        tax = TaxBillingSetting(
            client_id=order.client_id,
            branch_id=order.branch_id,
            default_tax_rate=5.0,
            cgst=2.5 if branch_tt == "GST" else 0.0,
            sgst=2.5 if branch_tt == "GST" else 0.0,
            service_charge=0.0,
            bill_footer_message="Thank you for dining with us!",
            enable_service_charge=False,
            enable_tax=True,
            round_off_bill=True,
        )
        db.add(tax)
        try:
            await db.flush()
        except Exception:
            pass

    bill_res = await db.execute(select(Bill).where(Bill.order_id == order.id))
    bill = bill_res.scalar_one_or_none()

    effective_bill_tax_type = (
        str(bill.tax_type).strip().upper()
        if (bill and getattr(bill, "tax_type", None) and str(bill.tax_type).strip())
        else effective_branch_tax_type
    )

    subtotal = sum(float(item.subtotal or (item.unit_price * item.quantity)) for item in order.order_items)
    subtotal = round_money(subtotal, decimal_places)

    if tax and tax.enable_tax:
        raw_tax_rate = float(tax.default_tax_rate or (float(tax.cgst or 0) + float(tax.sgst or 0)))
        tax_calc = calculate_tax_amounts(
            taxable_amount=subtotal,
            tax_rate=raw_tax_rate,
            tax_type=effective_bill_tax_type,
            decimal_places=decimal_places,
        )
        cgst_percent = tax_calc["cgst_rate"]
        cgst_amount = tax_calc["cgst_amount"]
        sgst_percent = tax_calc["sgst_rate"]
        sgst_amount = tax_calc["sgst_amount"]
        vat_percent = tax_calc["vat_rate"]
        vat_amount = tax_calc["vat_amount"]
        tax_total = tax_calc["tax_total"]
    else:
        cgst_percent = 0.0
        cgst_amount = 0.0
        sgst_percent = 0.0
        sgst_amount = 0.0
        vat_percent = 0.0
        vat_amount = 0.0
        tax_total = 0.0

    service_charge_percent = float(tax.service_charge or 0) if (tax and tax.enable_service_charge) else 0.0

    discount_amount = float(bill.discount_amount or 0.0) if bill else 0.0
    offer_discount = float(bill.offer_discount or 0.0) if bill else 0.0
    round_off_enabled = bool(tax.round_off_bill) if tax else True

    calculated = _calculate_bill_totals(
        subtotal=subtotal,
        tax_total=tax_total,
        service_charge_percent=service_charge_percent,
        discount_amount=discount_amount,
        offer_discount=offer_discount,
        round_off_enabled=round_off_enabled,
    )

    if not bill:
        bill = Bill(
            order_id=order.id,
            client_id=order.client_id,
            branch_id=order.branch_id,
            customer_id=order.customer_id,
            invoice_no=f"INV-{uuid4().hex[:8].upper()}",
            order_type=order.order_type.value if hasattr(order.order_type, "value") else str(order.order_type),
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            payment_status=PaymentStatus.pending,
            payment_method=None,
            subtotal=calculated["subtotal"],
            tax_type=effective_bill_tax_type,
            cgst_percent=cgst_percent,
            cgst_amount=cgst_amount,
            sgst_percent=sgst_percent,
            sgst_amount=sgst_amount,
            vat_percent=vat_percent,
            vat_amount=vat_amount,
            service_charge_percent=calculated["service_charge_percent"],
            service_charge_amount=calculated["service_charge_amount"],
            tax_total=calculated["tax_total"],
            discount_amount=discount_amount,
            round_off_amount=calculated["round_off_amount"],
            grand_total=calculated["grand_total"],
            offer_id=None,
            offer_discount=offer_discount,
            final_amount=calculated["final_amount"],
            paid_amount=0.0,
            due_amount=calculated["final_amount"],
            footer_message=tax.bill_footer_message if tax else "Thank you for dining with us!",
        )
        db.add(bill)
        await db.flush()
    elif bill.payment_status != PaymentStatus.complete:
        bill.customer_id = order.customer_id or bill.customer_id
        bill.subtotal = calculated["subtotal"]
        bill.tax_type = effective_bill_tax_type
        bill.cgst_percent = cgst_percent
        bill.cgst_amount = cgst_amount
        bill.sgst_percent = sgst_percent
        bill.sgst_amount = sgst_amount
        bill.vat_percent = vat_percent
        bill.vat_amount = vat_amount
        bill.tax_total = calculated["tax_total"]
        bill.service_charge_percent = calculated["service_charge_percent"]
        bill.service_charge_amount = calculated["service_charge_amount"]
        bill.discount_amount = discount_amount
        bill.offer_discount = offer_discount
        bill.round_off_amount = calculated["round_off_amount"]
        bill.grand_total = calculated["grand_total"]
        bill.final_amount = calculated["final_amount"]
        paid_amount = float(bill.paid_amount or 0)
        bill.due_amount = round_money(max(bill.final_amount - paid_amount, 0.0), decimal_places)
        await db.flush()

    return bill


async def complete_bill_transaction(
    db: AsyncSession,
    *,
    bill: Bill,
    payment_method: Optional[str] = None,
    paid_amount: Optional[float] = None,
    customer_id: Optional[int] = None,
) -> Bill:
    """
    AUTHORITATIVE BILL COMPLETION SERVICE

    Executes all shared post-payment/bill-completion business logic:
    1. Idempotency guard: No-op if already complete.
    2. Set bill payment_status = complete, paid_amount, due_amount = 0.
    3. Release table (TableStatus.available) & complete active RestaurantSession.
    4. Handle Customer CRM identification, CustomerVisitHistory, and stats via handle_customer_and_visit().
    5. Re-evaluate customer loyalty rank.
    6. Invalidate dashboard and invoice caches.
    7. Publish 'bill_completed' event to CRM stream.
    8. Send bill completed FCM notification.
    """
    # 1. Idempotency guard
    if bill.payment_status == PaymentStatus.complete:
        logger.info(f"[complete_bill_transaction] Bill #{bill.id} is already completed. Skipping duplicate processing.")
        return bill

    # 2. Update Bill Status
    bill.payment_status = PaymentStatus.complete
    final_paid = (
        paid_amount
        if paid_amount is not None
        else (bill.final_amount if bill.final_amount and bill.final_amount > 0 else (bill.grand_total or 0.0))
    )
    bill.paid_amount = round(float(final_paid), 2)
    bill.due_amount = 0.0
    if payment_method:
        bill.payment_method = payment_method
    elif not bill.payment_method:
        bill.payment_method = "cash"

    # 3. Release Table and Close Restaurant Session
    order = await db.get(Order, bill.order_id)
    table = None
    if order and order.table_id:
        table = await db.get(Table, order.table_id)
        if table:
            table.status = TableStatus.available
            await Cache.delete(f"tables:branch:{table.branch_id}")

        # Complete any active restaurant session on this table
        await db.execute(
            update(RestaurantSession)
            .where(
                RestaurantSession.table_id == order.table_id,
                RestaurantSession.status == SessionStatus.ACTIVE.value,
            )
            .values(status=SessionStatus.COMPLETED.value)
        )

    if order and order.restaurant_session_id:
        sess = await db.get(RestaurantSession, order.restaurant_session_id)
        if sess:
            sess.status = SessionStatus.COMPLETED.value

    # 4. Resolve Customer, Record Visit History, and Update CRM Stats
    branch = await db.get(Branch, bill.branch_id)
    branch_name = branch.name if branch else ""

    resolved_customer_id = customer_id or bill.customer_id or (order.customer_id if order else None)
    cust = None
    if resolved_customer_id:
        cust = await db.get(Customer, resolved_customer_id)

    c_name = cust.name if cust else (bill.customer_name or (order.customer_name if order else None))
    c_phone = cust.phone if cust else (bill.customer_phone or (order.customer_phone if order else None))
    c_email = cust.email if cust else None

    table_name = None
    if table:
        table_name = table.name if not getattr(table, "floor", None) else f"{table.name} ({table.floor})"

    visit_type_val = (
        order.order_type.value
        if order and hasattr(order.order_type, "value")
        else (str(order.order_type) if order and order.order_type else (bill.order_type or "Dine-In"))
    )

    customer = await handle_customer_and_visit(
        db=db,
        client_id=bill.client_id,
        branch_id=bill.branch_id,
        branch_name=branch_name,
        order_id=bill.order_id,
        bill_id=bill.id,
        total_amount=bill.final_amount or bill.grand_total or 0.0,
        discount=(bill.discount_amount or 0.0) + (bill.offer_discount or 0.0) + (getattr(bill, "wallet_discount", 0.0) or 0.0),
        tax=bill.tax_total or 0.0,
        payment_method=bill.payment_method,
        table_name=table_name,
        visit_type=visit_type_val,
        customer_name=c_name,
        customer_phone=c_phone,
        customer_email=c_email,
    )

    if customer:
        bill.customer_id = customer.id
        if order and not order.customer_id:
            order.customer_id = customer.id

        await calculate_customer_rank(
            db=db,
            customer=customer,
            branch_id=bill.branch_id,
        )

    await db.flush()

    # 5. Invalidate Caches
    await Cache.delete_pattern(f"dashboard:*:branch:{bill.branch_id}")
    await Cache.delete(f"invoice:pdf:{bill.id}")

    # 6. Publish CRM Event to Redis Stream
    try:
        from app.accounts.crm.events.publisher import crm_event_publisher

        await crm_event_publisher.publish_bill_completed(
            bill_id=bill.id,
            order_id=bill.order_id,
            customer_id=bill.customer_id or 0,
            client_id=bill.client_id,
            branch_id=bill.branch_id,
        )
    except Exception as err:
        logger.warning(f"[CRM Event Publisher Error]: {err}")

    # 7. Dispatch FCM Notification
    try:
        from app.accounts.notification.service import NotificationService

        await NotificationService.send_bill_completed(db, bill)
    except Exception as notif_err:
        logger.warning(f"[Notification Bill Completed Error]: {notif_err}")

    return bill


class InvoiceService:

    @staticmethod
    async def download_invoice(
        db,
        bill_id,
        client_id,
        branch_id,
    ):
        bill_res = await db.execute(
            select(Bill).where(
                Bill.id == bill_id,
                Bill.client_id == client_id,
                Bill.branch_id == branch_id,
            )
        )
        bill = bill_res.scalar_one_or_none()

        if not bill:
            raise HTTPException(status_code=404, detail="Invoice not found")

        pdf = BytesIO()
        await asyncio.to_thread(InvoiceTemplate.generate, pdf, bill)
        pdf.seek(0)

        return StreamingResponse(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{bill.invoice_no}.pdf"'},
        )