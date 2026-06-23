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
from datetime import datetime
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
from app.accounts.offer.model import Offer, OfferType
from app.accounts.bill.schema import BillOut, EditBillItemsRequest, EditBillResponse, OfferPreviewRequest, OfferPreviewResponse, BillStatusUpdate, BillStatusResponse

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
    # CREATE BILL IF NOT EXISTS
    # =====================================================



    if not bill:

        bill = Bill(

            order_id=order.id,

            client_id=order.client_id,

            branch_id=order.branch_id,

            invoice_no=f"INV-{uuid4().hex[:8].upper()}",

            order_type=order.order_type,

            customer_name=order.customer_name,

            payment_status=PaymentStatus.pending,

            customer_phone=order.customer_phone,

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

            service_charge_percent=service_charge_percent,

            service_charge_amount=service_charge_amount,

            tax_total=tax_total,

            discount_amount=0.0,

            round_off_amount=round_off_amount,

            grand_total=grand_total,

            # ==========================
            # OFFER DEFAULT VALUES
            # ==========================
            offer_id=None,
            offer_discount=0.0,

            # Amount customer has to pay
            final_amount=grand_total,

            paid_amount=0.0,

            due_amount=grand_total,

            footer_message=tax.bill_footer_message
        )

        db.add(bill)
        await db.commit()
        await db.refresh(bill)
    


    else:

        updated = False

        if bill.final_amount is None:
            bill.final_amount = bill.grand_total
            updated = True

        if bill.offer_discount is None:
            bill.offer_discount = 0.0
            updated = True

        if bill.due_amount is None:
            bill.due_amount = bill.final_amount
            updated = True

        if updated:
            await db.commit()
            await db.refresh(bill)

    # =====================================================
    # RETURN RESPONSE - SHOW ORIGINAL VALUES UNLESS PAID
    # =====================================================
    
    # is_bill_finalized = bill.payment_status in (
    #     PaymentStatus.complete,
    #     PaymentStatus.edited
    # )

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

        "grand_total": bill.grand_total,

        "paid_amount": bill.paid_amount,

        # Only show due amount as final if payment is complete
        # "due_amount": (bill.due_amount if is_bill_finalized else bill.grand_total),

        "footer_message": (
            bill.footer_message or ""
        ),
        "due_amount": bill.due_amount,

        "offer_id": bill.offer_id,

        "offer_discount": bill.offer_discount,

        "final_amount": bill.final_amount,

        "is_edited": bill.is_edited

        # Only show offer data if payment is complete
        # "offer_id": (bill.offer_id if is_bill_finalized else None),
        # "offer_discount": (bill.offer_discount if is_bill_finalized else 0.0),
        # "final_amount": (bill.final_amount if is_bill_finalized else bill.grand_total)
    }


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

        elif data.payment_status in [
            PaymentStatus.pending,
            PaymentStatus.edited,
        ]:
            table.status = TableStatus.occupied

        elif data.payment_status == PaymentStatus.cancel:
            table.status = TableStatus.occupied

    # FIXED: This block was incorrectly indented
    if data.payment_status == PaymentStatus.complete:
        bill.payment_status = PaymentStatus.complete
        bill.paid_amount = (
            bill.final_amount
            if bill.final_amount > 0
            else bill.grand_total
        )

        bill.due_amount = 0.0

    elif data.payment_status == PaymentStatus.cancel:

        bill.paid_amount = 0.0

        bill.due_amount = (
            bill.final_amount
            if bill.final_amount > 0
            else bill.grand_total
        )

    elif data.payment_status == PaymentStatus.edited:

        # Bill modified but not paid yet
        bill.paid_amount = 0.0

        bill.due_amount = (
            bill.final_amount
            if bill.final_amount > 0
            else bill.grand_total
        )

    await db.commit()
    await db.refresh(bill)

    return bill

# =====================================================
# OFFER PREVIEW ENDPOINT - NO DB UPDATES!
# =====================================================

@router.post(
    "/offer-preview",
    response_model=OfferPreviewResponse
)
async def preview_offer_application(
    data: OfferPreviewRequest,
    db: SessionDep
):
    # =====================================================
    # GET BILL
    # =====================================================
    bill_result = await db.execute(
        select(Bill)
        .where(Bill.id == data.bill_id)
    )
    bill = bill_result.scalar_one_or_none()
    
    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )
    
    # Original amount is always grand_total
    original_amount = bill.grand_total
    
    # If no offer, return original
    if not data.offer_id:

        bill.offer_id = None

        bill.offer_discount = 0.0

        bill.final_amount = bill.grand_total

        bill.due_amount = bill.grand_total

        # bill.payment_status = PaymentStatus.pending

        await db.commit()

        await db.refresh(bill)

        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            message="Offer removed"
        )
    # =====================================================
    # GET OFFER
    # =====================================================
    offer_result = await db.execute(
        select(Offer)
        .where(Offer.id == data.offer_id)
    )
    offer = offer_result.scalar_one_or_none()
    
    if not offer:
        raise HTTPException(
            status_code=404,
            detail="Offer not found"
        )
    
    # Check if offer is active
    if not offer.is_active:
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            message="Offer is not active"
        )
    
    # Check if offer is valid for current time
    now = datetime.utcnow()
    if not (offer.valid_from <= now <= offer.valid_to):
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            message="Offer is not valid at this time"
        )
    
    # Check minimum order amount
    if original_amount < offer.min_order_amount:
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            message=f"Minimum order amount of {offer.min_order_amount} required for this offer"
        )
    
    # =====================================================
    # CALCULATE DISCOUNT
    # =====================================================
    discount = 0.0
    
    if offer.offer_type == OfferType.FLAT_DISCOUNT:
        # Flat discount: subtract discount_value from total
        discount = min(offer.discount_value or 0, original_amount)
    
    elif offer.offer_type == OfferType.PERCENTAGE_OFF:
        # Percentage discount: calculate % of total
        discount = round(original_amount * (offer.discount_value / 100), 2)
    
    # For BUY_ONE_GET_ONE and FREE_ITEM, we'd need more order details,
    # but for now we'll treat them as no discount since we don't have item breakdown in bill
    else:
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            message="Offer type requires more order details"
        )
    
    # Calculate final amount
    # Calculate final amount
    final_amount = max(
        0,
        original_amount - discount
    )

# ==========================================
# SAVE OFFER ON BILL
# ==========================================

    bill.offer_id = offer.id

    bill.offer_discount = discount

    bill.final_amount = final_amount

    bill.due_amount = final_amount

    # bill.payment_status = PaymentStatus.edited

    await db.commit()

    await db.refresh(bill)

    return OfferPreviewResponse(
        original_amount=original_amount,
        offer_discount=discount,
        final_amount=final_amount,
        message=f"Offer applied: {offer.offer_name}"
    )


@router.patch(
    "/edit/{bill_id}",
    response_model=EditBillResponse
)
async def edit_bill(
    bill_id: int,
    db: SessionDep
):
    bill = await db.get(
        Bill,
        bill_id
    )

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    if bill.payment_status != PaymentStatus.cancel:
        raise HTTPException(
            status_code=400,
            detail="Only canceled bills can be edited"
        )

    bill.is_edited = True

    await db.commit()
    await db.refresh(bill)

    return bill

from sqlalchemy import select

from app.accounts.order.model import Order, OrderItem

from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing

from app.accounts.offer.model import Offer, OfferType

from app.accounts.bill.enum import PaymentStatus


@router.patch(
    "/{bill_id}/order-items",
    response_model=EditBillResponse
)
async def edit_bill_items(
    bill_id: int,
    data: EditBillItemsRequest,
    db: SessionDep
):
    # =====================================================
    # BILL
    # =====================================================

    bill = await db.get(
        Bill,
        bill_id
    )

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # =====================================================
    # ONLY CANCELED BILL CAN BE EDITED
    # =====================================================

    if bill.payment_status != PaymentStatus.cancel:
        raise HTTPException(
            status_code=400,
            detail="Only canceled bills can be edited"
        )

    # =====================================================
    # ORDER
    # =====================================================

    order = await db.get(
        Order,
        bill.order_id
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # =====================================================
    # ADD / UPDATE / DELETE ITEMS
    # =====================================================

    for item_data in data.items:

        result = await db.execute(
            select(OrderItem).where(
                OrderItem.order_id == order.id,
                OrderItem.item_id == item_data.item_id
            )
        )

        order_item = result.scalar_one_or_none()

        # ================================================
        # DELETE ITEM
        # ================================================

        if item_data.quantity <= 0:

            if order_item:
                await db.delete(order_item)

            continue

        # ================================================
        # UPDATE EXISTING ITEM
        # ================================================

        if order_item:

            order_item.quantity = item_data.quantity

            order_item.total_price = round(
                float(order_item.price or 0)
                * item_data.quantity,
                2
            )

            continue

        # ================================================
        # ADD NEW ITEM
        # ================================================

        menu_item = await db.get(
            Item,
            item_data.item_id
        )

        if not menu_item:
            raise HTTPException(
                status_code=404,
                detail=f"Item {item_data.item_id} not found"
            )

        pricing_result = await db.execute(
            select(Pricing).where(
                Pricing.item_id == menu_item.id
            )
        )

        pricing = pricing_result.scalar_one_or_none()

        if not pricing:
            raise HTTPException(
                status_code=404,
                detail=f"Pricing not found for item {menu_item.id}"
            )

        new_order_item = OrderItem(
            order_id=order.id,
            item_id=menu_item.id,
            quantity=item_data.quantity,
            price=pricing.total_price,
            total_price=round(
                float(pricing.total_price or 0)
                * item_data.quantity,
                2
            )
        )

        db.add(new_order_item)

    await db.flush()

    # =====================================================
    # RELOAD ITEMS
    # =====================================================

    result = await db.execute(
        select(OrderItem).where(
            OrderItem.order_id == order.id
        )
    )

    order_items = result.scalars().all()

    if not order_items:
        raise HTTPException(
            status_code=400,
            detail="Order must contain at least one item"
        )

    # =====================================================
    # SUBTOTAL
    # =====================================================

    subtotal = round(
        sum(
            float(i.total_price or 0)
            for i in order_items
        ),
        2
    )

    # =====================================================
    # TAX
    # =====================================================

    cgst_amount = round(
        subtotal *
        (bill.cgst_percent / 100),
        2
    )

    sgst_amount = round(
        subtotal *
        (bill.sgst_percent / 100),
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

    service_charge_amount = round(
        subtotal *
        (
            bill.service_charge_percent / 100
        ),
        2
    )

    # =====================================================
    # GRAND TOTAL
    # =====================================================

    grand_total = round(
        subtotal +
        tax_total +
        service_charge_amount,
        2
    )

    # =====================================================
    # OFFER
    # =====================================================

    final_amount = grand_total
    bill.offer_discount = 0

    if bill.offer_id:

        offer = await db.get(
            Offer,
            bill.offer_id
        )

        if offer:

            discount = 0

            if (
                offer.offer_type ==
                OfferType.FLAT_DISCOUNT
            ):
                discount = min(
                    float(
                        offer.discount_value or 0
                    ),
                    grand_total
                )

            elif (
                offer.offer_type ==
                OfferType.PERCENTAGE_OFF
            ):
                discount = round(
                    grand_total *
                    (
                        offer.discount_value / 100
                    ),
                    2
                )

            bill.offer_discount = discount

            final_amount = round(
                grand_total -
                discount,
                2
            )

    # =====================================================
    # UPDATE BILL
    # =====================================================

    bill.subtotal = subtotal

    bill.cgst_amount = cgst_amount

    bill.sgst_amount = sgst_amount

    bill.tax_total = tax_total

    bill.service_charge_amount = (
        service_charge_amount
    )

    bill.grand_total = grand_total

    bill.final_amount = final_amount

    bill.due_amount = final_amount

    bill.payment_status = (
        PaymentStatus.edited
    )

    bill.is_edited = True

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()

    await db.refresh(bill)

    return bill