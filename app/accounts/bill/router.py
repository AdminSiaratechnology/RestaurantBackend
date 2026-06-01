# =========================================================
# FILE: app/accounts/bill/router.py
# =========================================================

# pyrefly: ignore [missing-import]
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
from app.accounts.bill.enum import PaymentStatus

from app.accounts.tax.model import TaxBillingSetting

from app.accounts.bill.model import Bill

from app.accounts.bill.schema import BillOut

from app.accounts.pricing.model import Pricing

from app.accounts.table.model import Table
from app.accounts.table.schema import TableStatus
router = APIRouter(
    prefix="/bill",
    tags=["Bill"]
)


# =========================================================
# SERVICE CHARGE HELPERS
# =========================================================

def _service_charge_rate(
    tax: TaxBillingSetting
) -> float:

    return float(
        tax.service_charge or 0.0
    )


def _compute_service_charge(
    tax: TaxBillingSetting,
    subtotal: float,
) -> tuple[float, float]:

    percent = _service_charge_rate(tax)

    if percent <= 0:

        return 0.0, 0.0

    return (
        percent,
        round(
            subtotal * (percent / 100),
            2
        )
    )


# =========================================================
# GET BILL
# =========================================================

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
    # ITEMS + SUBTOTAL + PRICING
    # =====================================================

    items = []

    subtotal = 0.0

    for order_item in order.order_items:

        item_total = float(
            order_item.total_price or 0.0
        )

        if (
            item_total <= 0
            and order_item.quantity
        ):

            item_total = round(
                order_item.quantity *
                order_item.price,
                2,
            )

        subtotal += item_total

        # =================================================
        # GET ITEM
        # =================================================

        item = order_item.item

        # =================================================
        # GET PRICINGS
        # =================================================

        pricing_result = await db.execute(
            select(Pricing).where(
                Pricing.item_id == item.id,
                Pricing.client_id == order.client_id,
                Pricing.branch_id == order.branch_id
            )
        )

        pricings = pricing_result.scalars().all()

        pricing_list = []

        for pricing in pricings:

            tax_percent = float(
                pricing.tax or 0
            )

            price = float(
                pricing.price or 0
            )

            discount = float(
                pricing.discount or 0
            )

            discounted_price = round(
                price - discount,
                2
            )

            cgst_rate = float(
                pricing.cgst_rate or 0
            )

            sgst_rate = float(
                pricing.sgst_rate or 0
            )

            cgst_amount = round(
                discounted_price * (
                    cgst_rate / 100
                ),
                2
            )

            sgst_amount = round(
                discounted_price * (
                    sgst_rate / 100
                ),
                2
            )

            total_tax_amount = round(
                cgst_amount +
                sgst_amount,
                2
            )

            total_price = round(
                discounted_price +
                total_tax_amount,
                2
            )

            pricing_list.append({

                "id": pricing.id,

                "client_id": pricing.client_id,

                "branch_id": pricing.branch_id,

                "item_id": pricing.item_id,

                "price": pricing.price,

                "cost_price": pricing.cost_price,

                "discount": pricing.discount,

                "tax": pricing.tax,

                "calories": pricing.calories,

                "is_active": pricing.is_active,

                "created_at": pricing.created_at,

                "cgst_rate": cgst_rate,

                "sgst_rate": sgst_rate,

                "discounted_price": discounted_price,

                "cgst_amount": cgst_amount,

                "sgst_amount": sgst_amount,

                "total_tax_amount": total_tax_amount,

                "total_price": total_price
            })

        # =================================================
        # APPEND ITEM
        # =================================================

        items.append({

            "id": item.id,

            "name": item.name,

            "client_id": item.client_id,

            "category_id": item.category_id,

            "branch_id": item.branch_id,

            "created_at": item.created_at,

            "is_active": item.is_active,

            "pricings": pricing_list
        })

    subtotal = round(
        subtotal,
        2
    )

    # =====================================================
    # TAXES
    # =====================================================

    cgst_amount = 0.0

    sgst_amount = 0.0

    if tax.enable_tax:

        cgst_amount = round(
            subtotal * (
                tax.cgst / 100
            ),
            2
        )

        sgst_amount = round(
            subtotal * (
                tax.sgst / 100
            ),
            2
        )

    tax_total = round(
        cgst_amount +
        sgst_amount,
        2
    )

    # =====================================================
    # SERVICE CHARGE
    # =====================================================

    (
        service_charge_percent,
        service_charge_amount
    ) = _compute_service_charge(
        tax,
        subtotal
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

        rounded_total = round(
            calculated_total
        )

        round_off_amount = round(
            rounded_total -
            calculated_total,
            2
        )

        grand_total = rounded_total

    else:

        grand_total = round(
            calculated_total,
            2
        )



    # =====================================================
    # CHECK EXISTING BILL
    # =====================================================

    bill_result = await db.execute(
        select(Bill)
        .where(
            Bill.order_id == order.id
        )
    )

    bill = (
        bill_result.scalar_one_or_none()
    )



    # =====================================================
    # CREATE BILL
    # =====================================================

    if not bill:

        bill = Bill(

            order_id=order.id,

            client_id=order.client_id,

            branch_id=order.branch_id,

            invoice_no=(
                f"INV-{uuid4().hex[:8].upper()}"
            ),

            order_type=order.order_type,

            customer_name=order.customer_name,

            customer_phone=order.customer_phone,

            # payment_status=PaymentStatus.pending,

            payment_method=None,

            subtotal=subtotal,

            cgst_percent=(
                tax.cgst
                if tax.enable_tax
                else 0.0
            ),

            cgst_amount=cgst_amount,

            sgst_percent=(
                tax.sgst
                if tax.enable_tax
                else 0.0
            ),

            sgst_amount=sgst_amount,

            service_charge_percent=(
                service_charge_percent
            ),

            service_charge_amount=(
                service_charge_amount
            ),

            tax_total=tax_total,

            discount_amount=(
                discount_amount
            ),

            round_off_amount=(
                round_off_amount
            ),

            grand_total=grand_total,

            paid_amount=0.0,

            due_amount=grand_total,

            footer_message=(
                tax.bill_footer_message
            )
        )

        db.add(bill)

    # =====================================================
    # UPDATE BILL
    # =====================================================

    else:

        bill.customer_name = (
            order.customer_name
        )

        bill.customer_phone = (
            order.customer_phone
        )

        # ==========================================
        # DO NOT RESET PAYMENT STATUS
        # ==========================================

        bill.subtotal = subtotal

        bill.cgst_percent = (
            tax.cgst
            if tax.enable_tax
            else 0.0
        )

        bill.cgst_amount = cgst_amount

        bill.sgst_percent = (
            tax.sgst
            if tax.enable_tax
            else 0.0
        )

        bill.sgst_amount = sgst_amount

        bill.service_charge_percent = (
            service_charge_percent
        )

        bill.service_charge_amount = (
            service_charge_amount
        )

        bill.tax_total = tax_total

        bill.discount_amount = (
            discount_amount
        )

        bill.round_off_amount = (
            round_off_amount
        )

        bill.grand_total = grand_total

        # ==========================================
        # UPDATE AMOUNTS BASED ON CURRENT STATUS
        # ==========================================

        if bill.payment_status == PaymentStatus.complete:

            bill.paid_amount = grand_total
            bill.due_amount = 0.0

        elif bill.payment_status == PaymentStatus.cancel:

            bill.paid_amount = 0.0
            bill.due_amount = grand_total

        else:

            bill.paid_amount = 0.0
            bill.due_amount = grand_total

        bill.footer_message = (
            tax.bill_footer_message
        )

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()

    await db.refresh(bill)
    # if order.table_id:
    #     table = await db.get(
    #         Table,
    #         order.table_id
    #     )

    #     if not table:
    #         raise HTTPException(
    #             status_code=404,
    #             detail="Table not found"
    #         )

    #     table.status = TableStatus.available
    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "id": bill.id,

        "order_id": bill.order_id,

        "invoice_no": bill.invoice_no,

        "order_type": bill.order_type,

        "customer_name": (
            bill.customer_name
        ),

        "customer_phone": (
            bill.customer_phone
        ),

        "table_id": order.table_id,

        "payment_status": (
            bill.payment_status
        ),

        "payment_method": (
            bill.payment_method
        ),

        "created_at": bill.created_at,

        "items": items,

        "subtotal": bill.subtotal,

        "cgst_percent": (
            bill.cgst_percent
        ),

        "cgst_amount": (
            bill.cgst_amount
        ),

        "sgst_percent": (
            bill.sgst_percent
        ),

        "sgst_amount": (
            bill.sgst_amount
        ),

        "service_charge_percent": (
            bill.service_charge_percent
        ),

        "service_charge_amount": (
            bill.service_charge_amount
        ),

        "tax_total": (
            bill.tax_total
        ),

        "discount_amount": (
            bill.discount_amount
        ),

        "round_off_amount": (
            bill.round_off_amount
        ),

        "grand_total": (
            bill.grand_total
        ),

        "paid_amount": (
            bill.paid_amount
        ),

        "due_amount": (
            bill.due_amount
        ),

        "footer_message": (
            bill.footer_message or ""
        )
    }

from app.accounts.bill.schema import BillStatusUpdate, BillStatusResponse

@router.patch(
    "/status/{bill_id}",
    response_model=BillStatusResponse
)
async def update_bill_status(
    bill_id: int,
    data: BillStatusUpdate,
    db: SessionDep
):
    result = await db.execute(
        select(Bill).where(
            Bill.id == bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # ==========================================
    # ALREADY UPDATED
    # ==========================================

    if bill.payment_status in [
        PaymentStatus.complete,
        PaymentStatus.cancel
    ]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bill already marked as "
                f"{bill.payment_status}"
            )
        )

    # ==========================================
    # UPDATE STATUS
    # ==========================================

    bill.payment_status = data.payment_status

    order = await db.get(
        Order,
        bill.order_id
    )

    if order and order.table_id:

        table = await db.get(
            Table,
            order.table_id
        )

        if data.payment_status == PaymentStatus.complete:
            table.status = TableStatus.available
        else:
            table.status = TableStatus.occupied

    if data.payment_status == PaymentStatus.complete:

        bill.paid_amount = bill.grand_total
        bill.due_amount = 0.0

    elif data.payment_status == PaymentStatus.cancel:

        bill.paid_amount = 0.0
        bill.due_amount = bill.grand_total

    await db.commit()
    await db.refresh(bill)

    return bill