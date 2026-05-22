# =========================================================
# FILE: app/accounts/bill/router.py
# =========================================================

# pyrefly: ignore [missing-import]

from fastapi import APIRouter, HTTPException
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.config import SessionDep

from app.accounts.order.model import (
    Order,
    OrderItem
)

from app.accounts.tax.model import TaxBillingSetting

from app.accounts.bill.model import Bill

from app.accounts.bill.schema import BillOut


router = APIRouter(
    prefix="/bill",
    tags=["Bill"]
)


@router.get(
    "/{order_id}",
    response_model=BillOut
)
async def get_bill(
    order_id: int,
    db: SessionDep
):

    # =====================================================
    # GET ORDER
    # =====================================================

    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.order_items)
            .selectinload(OrderItem.item)
        )
        .where(Order.id == order_id)
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # =====================================================
    # GET TAX SETTINGS
    # =====================================================

    tax_result = await db.execute(
        select(TaxBillingSetting)
        .where(
            TaxBillingSetting.branch_id == order.branch_id
        )
    )

    tax = tax_result.scalar_one_or_none()

    if not tax:
        raise HTTPException(
            status_code=404,
            detail="Tax settings not found"
        )

    # =====================================================
    # ITEMS + SUBTOTAL
    # =====================================================

    items = []

    subtotal = 0.0

    for order_item in order.order_items:

        item_total = (
            order_item.quantity *
            order_item.price
        )

        subtotal += item_total

        items.append({
            "item_id": order_item.item.id,
            "item_name": order_item.item.name,
            "quantity": order_item.quantity,
            "price": round(order_item.price, 2),
            "total": round(item_total, 2)
        })

    subtotal = round(subtotal, 2)

    # =====================================================
    # TAXES
    # =====================================================

    cgst_amount = 0.0
    sgst_amount = 0.0

    if tax.enable_tax:

        cgst_amount = round(
            subtotal * (tax.cgst / 100),
            2
        )

        sgst_amount = round(
            subtotal * (tax.sgst / 100),
            2
        )

    tax_total = round(
        cgst_amount + sgst_amount,
        2
    )

    # =====================================================
    # SERVICE CHARGE
    # =====================================================

    service_charge_amount = 0.0

    if tax.enable_service_charge:

        service_charge_amount = round(
            subtotal * (tax.service_charge / 100),
            2
        )

    # =====================================================
    # DISCOUNT
    # =====================================================

    discount_amount = 0.0

    # =====================================================
    # GRAND TOTAL
    # =====================================================

    calculated_total = (
        subtotal +
        tax_total +
        service_charge_amount -
        discount_amount
    )

    round_off_amount = 0.0

    if tax.round_off_bill:

        rounded_total = round(calculated_total)

        round_off_amount = round(
            rounded_total - calculated_total,
            2
        )

        grand_total = rounded_total

    else:

        grand_total = round(
            calculated_total,
            2
        )

    # =====================================================
    # PAYMENT
    # =====================================================

    paid_amount = grand_total \
        if order.status.lower() == "paid" \
        else 0.0

    due_amount = round(
        grand_total - paid_amount,
        2
    )

    # =====================================================
    # CHECK EXISTING BILL
    # =====================================================

    bill_result = await db.execute(
        select(Bill)
        .where(Bill.order_id == order.id)
    )

    bill = bill_result.scalar_one_or_none()

    # =====================================================
    # CREATE BILL
    # =====================================================

    if not bill:

        bill = Bill(

            order_id=order.id,

            client_id=order.client_id,

            branch_id=order.branch_id,

            invoice_no=f"INV-{uuid4().hex[:8].upper()}",

            order_type=order.order_type,

            customer_name=order.customer_name,

            customer_phone=order.customer_phone,

            payment_status=order.status,

            payment_method=None,

            subtotal=subtotal,

            cgst_percent=tax.cgst if tax.enable_tax else 0.0,

            cgst_amount=cgst_amount,

            sgst_percent=tax.sgst if tax.enable_tax else 0.0,

            sgst_amount=sgst_amount,

            service_charge_percent=(
                tax.service_charge
                if tax.enable_service_charge
                else 0.0
            ),

            service_charge_amount=service_charge_amount,

            tax_total=tax_total,

            discount_amount=discount_amount,

            round_off_amount=round_off_amount,

            grand_total=grand_total,

            paid_amount=paid_amount,

            due_amount=due_amount,

            footer_message=tax.bill_footer_message
        )

        db.add(bill)

    # =====================================================
    # UPDATE BILL
    # =====================================================

    else:

        bill.customer_name = order.customer_name

        bill.customer_phone = order.customer_phone

        bill.payment_status = order.status

        bill.subtotal = subtotal

        bill.cgst_percent = (
            tax.cgst if tax.enable_tax else 0.0
        )

        bill.cgst_amount = cgst_amount

        bill.sgst_percent = (
            tax.sgst if tax.enable_tax else 0.0
        )

        bill.sgst_amount = sgst_amount

        bill.service_charge_percent = (
            tax.service_charge
            if tax.enable_service_charge
            else 0.0
        )

        bill.service_charge_amount = (
            service_charge_amount
        )

        bill.tax_total = tax_total

        bill.discount_amount = discount_amount

        bill.round_off_amount = round_off_amount

        bill.grand_total = grand_total

        bill.paid_amount = paid_amount

        bill.due_amount = due_amount

        bill.footer_message = (
            tax.bill_footer_message
        )

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()

    await db.refresh(bill)

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "order_id": bill.order_id,

        "invoice_no": bill.invoice_no,

        "order_type": bill.order_type,

        "customer_name": bill.customer_name,

        "customer_phone": bill.customer_phone,

        "table_id": order.table_id,

        "payment_status": bill.payment_status,

        "payment_method": bill.payment_method,

        "created_at": bill.created_at,

        "items": items,

        "subtotal": bill.subtotal,

        "cgst_percent": bill.cgst_percent,

        "cgst_amount": bill.cgst_amount,

        "sgst_percent": bill.sgst_percent,

        "sgst_amount": bill.sgst_amount,

        "service_charge_percent": (
            bill.service_charge_percent
        ),

        "service_charge_amount": (
            bill.service_charge_amount
        ),

        "tax_total": bill.tax_total,

        "discount_amount": (
            bill.discount_amount
        ),

        "round_off_amount": (
            bill.round_off_amount
        ),

        "grand_total": bill.grand_total,

        "paid_amount": bill.paid_amount,

        "due_amount": bill.due_amount,

        "footer_message": (
            bill.footer_message or ""
        )
    }