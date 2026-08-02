from uuid import uuid4
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app.db.config import get_db
from app.accounts.bill.service import InvoiceService
from app.accounts.deps import get_current_user, UserRole
from app.db.config import SessionDep
from sqlalchemy.ext.asyncio import AsyncSession
from app.accounts.order.model import (
    Order,
    OrderItem
)
from app.accounts.bill.enum import PaymentStatus

from app.accounts.tax.model import TaxBillingSetting

from app.accounts.bill.model import Bill
from app.accounts.offer.model import Offer, OfferType
from app.accounts.bill.schema import AddBillItemRequest, BillOut, EditBillItemsRequest, EditBillResponse, OfferPreviewRequest, OfferPreviewResponse, BillStatusUpdate, BillStatusResponse

from app.accounts.pricing.model import Pricing

from app.accounts.table.model import Table
from app.accounts.table.schema import TableStatus
from app.core.cache import Cache

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

        # BUG #5 FIX: Invalidate dashboard cache when a new bill is generated.
        # This was previously dead code placed after the return statement.
        await Cache.delete_pattern(f"dashboard:*:branch:{order.branch_id}")
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
        "branch_id": bill.branch_id,
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

    # NOTE: Cache invalidation was previously dead code (after return).
    # It is now correctly placed before the return above inside the
    # `if not bill:` block implicitly via the commit path. Nothing more needed here.


# =========================================================
# OFFER PREVIEW — POST /bill/offer-preview
# Returns a discount preview without persisting anything.
# =========================================================

@router.post(
    "/offer-preview",
    response_model=OfferPreviewResponse
)
async def offer_preview(
    data: OfferPreviewRequest,
    db: SessionDep
):
    # --------------------------------------------------
    # 1. Fetch Bill
    # --------------------------------------------------
    bill_result = await db.execute(
        select(Bill).where(Bill.id == data.bill_id)
    )
    bill = bill_result.scalar_one_or_none()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    grand_total = float(bill.grand_total or 0)
    paid_amount = float(bill.paid_amount or 0)

    offer_discount = 0.0
    message = None

    # --------------------------------------------------
    # 2. Calculate Offer Discount (if offer_id provided)
    # --------------------------------------------------
    if data.offer_id is not None:
        offer_result = await db.execute(
            select(Offer).where(Offer.id == data.offer_id)
        )
        offer = offer_result.scalar_one_or_none()

        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        if not offer.is_active:
            raise HTTPException(status_code=400, detail="Offer is not active")

        now = datetime.utcnow()
        if offer.valid_from and now < offer.valid_from:
            raise HTTPException(status_code=400, detail="Offer has not started yet")
        if offer.valid_to and now > offer.valid_to:
            raise HTTPException(status_code=400, detail="Offer has expired")

        if offer.min_order_amount and grand_total < offer.min_order_amount:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum order amount ₹{offer.min_order_amount:.2f} not met"
            )

        if offer.offer_type == OfferType.FLAT_DISCOUNT:
            offer_discount = min(float(offer.discount_value or 0), grand_total)

        elif offer.offer_type == OfferType.PERCENTAGE_OFF:
            offer_discount = round(grand_total * (float(offer.discount_value or 0) / 100), 2)

        # BUY_ONE_GET_ONE / FREE_ITEM — no numeric discount in preview
        else:
            offer_discount = 0.0
            message = f"Offer '{offer.offer_name}' applied — discount calculated at checkout"

        message = message or f"Offer '{offer.offer_name}' applied"

    final_amount = round(grand_total - offer_discount, 2)
    due_amount = round(max(final_amount - paid_amount, 0), 2)

    return OfferPreviewResponse(
        original_amount=grand_total,
        offer_discount=offer_discount,
        final_amount=final_amount,
        due_amount=due_amount,
        message=message,
    )



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

        if table:
            if data.payment_status == PaymentStatus.complete:
                table.status = TableStatus.available
            elif data.payment_status in [
                PaymentStatus.pending,
                PaymentStatus.edited,
            ]:
                table.status = TableStatus.occupied
            elif data.payment_status == PaymentStatus.cancel:
                table.status = TableStatus.occupied
            
            await Cache.delete(f"tables:branch:{table.branch_id}")

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

    # Invalidate dashboard cache (payment completed / bill status changed)
    await Cache.delete_pattern(f"dashboard:*:branch:{bill.branch_id}")

    # Invalidate invoice PDF cache since bill status changed
    await Cache.delete(f"invoice:pdf:{bill.id}")

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
        # bill.offer_id = None
        # bill.offer_discount = 0.0
        # bill.final_amount = bill.grand_total
        # bill.due_amount = bill.grand_total

        # bill.payment_status = PaymentStatus.pending

        # await db.commit()
        # await db.refresh(bill)

        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
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
            due_amount=original_amount,
            message="Offer is not active"
        )
    
    # Check if offer is valid for current time
    now = datetime.utcnow()
    if not (offer.valid_from <= now <= offer.valid_to):
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
            message="Offer is not valid at this time"
        )
    
    # Check minimum order amount
    if original_amount < offer.min_order_amount:
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
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
            due_amount=original_amount,
            message="Offer type requires more order details"
        )
    
    # Calculate final amount
    final_amount = max(
        0,
        original_amount - discount
    )

    # ==========================================
    # SAVE OFFER ON BILL
    # ==========================================

    # bill.offer_id = offer.id
    # bill.offer_discount = discount
    # bill.final_amount = final_amount
    # bill.due_amount = final_amount

    # bill.payment_status = PaymentStatus.edited

    # await db.commit()
    # await db.refresh(bill)

    return OfferPreviewResponse(
        original_amount=original_amount,
        offer_discount=discount,
        final_amount=final_amount,
        due_amount=final_amount,
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

    # Invalidate invoice PDF cache since bill was edited
    await Cache.delete(f"invoice:pdf:{bill_id}")

    # Invalidate dashboard cache
    await Cache.delete_pattern(f"dashboard:*:branch:{bill.branch_id}")

    return bill


from sqlalchemy import select
from app.accounts.order.model import Order, OrderItem
from app.core.cache import Cache
import base64
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
    # BUG #1 FIX: Allow editing of pending, edited, AND cancelled bills.
    # Only completely-paid bills must not be modified.
    # =====================================================

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Completed bills cannot be edited"
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
            pricing_result = await db.execute(
                select(Pricing).where(
                    Pricing.item_id == order_item.item_id,
                    Pricing.client_id == bill.client_id,
                    Pricing.branch_id == bill.branch_id
                )
            )

            pricing = pricing_result.scalar_one_or_none()

            if not pricing:
                raise HTTPException(
                    status_code=404,
                    detail=f"Pricing not found for item {order_item.item_id}"
                )

            unit_price = float(pricing.price or 0)
            discount_percent = float(pricing.discount or 0)
            tax_percent = float(pricing.tax or 0)

            discounted_price = unit_price - (
                unit_price * discount_percent / 100
            )

            tax_per_unit = discounted_price * tax_percent / 100

            subtotal = round(
                discounted_price * item_data.quantity,
                2
            )

            tax_amount = round(
                tax_per_unit * item_data.quantity,
                2
            )

            total_price = round(
                subtotal + tax_amount,
                2
            )

            order_item.unit_price = unit_price
            order_item.discount_percent = discount_percent
            order_item.tax_percent = tax_percent
            order_item.quantity = item_data.quantity
            order_item.subtotal = subtotal
            order_item.tax_amount = tax_amount
            order_item.total_price = total_price
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
                Pricing.item_id == menu_item.id,
                Pricing.client_id == bill.client_id,
                Pricing.branch_id == bill.branch_id,
                Pricing.is_active == True
            )
        )

        pricing = pricing_result.scalar_one_or_none()

        if not pricing:
            raise HTTPException(
                status_code=404,
                detail=f"Pricing not found for item {menu_item.id}"
            )

        unit_price = float(pricing.price or 0)
        discount_percent = float(pricing.discount or 0)
        tax_percent = float(pricing.tax or 0)

        discounted_price = unit_price - (
            unit_price * discount_percent / 100
        )

        tax_per_unit = discounted_price * tax_percent / 100

        subtotal = round(
            discounted_price * item_data.quantity,
            2
        )

        tax_amount = round(
            tax_per_unit * item_data.quantity,
            2
        )

        total_price = round(
            subtotal + tax_amount,
            2
        )

        new_order_item = OrderItem(
            order_id=order.id,
            item_id=menu_item.id,
            quantity=item_data.quantity,
            unit_price=unit_price,
            discount_percent=discount_percent,
            tax_percent=tax_percent,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_price=total_price,
            # BUG #3a FIX: Mark new items as "served" so the frontend
            # order-level served filter does not hide the bill after edit.
            order_status="served",
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
    # RECALCULATE ORDER TOTAL
    # =====================================================

    order.total_amount = round(
        sum(
            float(i.total_price or 0)
            for i in order_items
        ),
        2
    )

    # =====================================================
    # SUBTOTAL
    # =====================================================

    subtotal = round(
        sum(
            float(i.subtotal or 0)
            for i in order_items
        ),
        2
    )

    tax_total = round(
        sum(
            float(i.tax_amount or 0)
            for i in order_items
        ),
        2
    )

    cgst_amount = round(
        tax_total / 2,
        2
    )

    sgst_amount = round(
        tax_total / 2,
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
    bill.service_charge_amount = service_charge_amount
    bill.grand_total = grand_total
    bill.final_amount = final_amount
    bill.due_amount = final_amount

    order.total_amount = final_amount

    bill.payment_status = PaymentStatus.edited
    bill.is_edited = True

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()
    await db.refresh(bill)

    # BUG #4 FIX: Invalidate invoice PDF and dashboard caches after edit.
    # The previous code was missing these invalidations entirely.
    await Cache.delete(f"invoice:pdf:{bill.id}")
    await Cache.delete_pattern(
        f"dashboard:*:branch:{bill.branch_id}"
    )

    return bill


from app.accounts.bill.invoice_template import InvoiceTemplate

@router.get("/invoice/{bill_id}")
async def download_invoice(
    bill_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user = current_user["user"]
    role = current_user["role"]

    client_id = None
    branch_id = None

    if role == UserRole.STAFF:
        client_id = getattr(user, "client_id", None)
        branch_id = getattr(user, "branch_id", None)
    elif role == UserRole.CLIENT:
        client_id = user.id

    cache_key = f"invoice:pdf:{bill_id}"
    cached_b64 = await Cache.get(cache_key)
    if cached_b64:
        pdf_bytes = base64.b64decode(cached_b64)
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="INV-{bill_id}.pdf"'
            }
        )

    bill = await get_bill_for_invoice(
        db=db,
        bill_id=bill_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    pdf = BytesIO()

    InvoiceTemplate.generate(
        pdf,
        bill,
    )

    pdf_bytes = pdf.getvalue()
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    await Cache.set(cache_key, b64_pdf, expire=86400) # 24 hours

    pdf.seek(0)

    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{bill.invoice_no}.pdf"'
        },
    )


async def get_bill_for_invoice(
    db: AsyncSession,
    bill_id: int,
    client_id: int = None,
    branch_id: int = None,
):
    query = select(Bill).options(
        selectinload(Bill.branch),
        selectinload(Bill.order)
            .selectinload(Order.order_items)
            .selectinload(OrderItem.item)
    )

    conditions = [Bill.id == bill_id]
    if client_id is not None:
        conditions.append(Bill.client_id == client_id)
    if branch_id is not None:
        conditions.append(Bill.branch_id == branch_id)

    result = await db.execute(query.where(*conditions))

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # Dynamically calculate item-level CGST and SGST for PDF
    item_cgst = 0.0
    item_sgst = 0.0
    computed_subtotal = 0.0

    for order_item in bill.order.order_items:
        pricing_result = await db.execute(
            select(Pricing).where(
                Pricing.item_id == order_item.item_id,
                Pricing.branch_id == bill.branch_id
            )
        )
        pricing = pricing_result.scalars().first()
        
        if pricing:
            price = float(pricing.price or 0)
            discount = float(pricing.discount or 0)
            discounted_price = round(price - discount, 2)
            cgst_rate = float(pricing.cgst_rate or 0)
            sgst_rate = float(pricing.sgst_rate or 0)
            
            cgst_amt = round(discounted_price * (cgst_rate / 100), 2)
            sgst_amt = round(discounted_price * (sgst_rate / 100), 2)
            
            qty = order_item.quantity or 1
            item_cgst += cgst_amt * qty
            item_sgst += sgst_amt * qty
            computed_subtotal += price * qty
            
            # Override for the PDF display
            order_item.total_price = price * qty
            order_item.unit_price = price

    bill.cgst_amount = item_cgst
    bill.sgst_amount = item_sgst
    bill.tax_total = item_cgst + item_sgst
    bill.subtotal = computed_subtotal

    # Recalculate Grand Total
    service_charge = float(bill.service_charge_amount or 0)
    discount_amount = float(bill.discount_amount or 0)
    calculated_total = bill.subtotal + bill.tax_total + service_charge - discount_amount
    
    rounded_total = round(calculated_total)
    bill.round_off_amount = round(rounded_total - calculated_total, 2)
    bill.grand_total = rounded_total

    if bill.payment_status == PaymentStatus.pending:
        bill.final_amount = bill.grand_total
        bill.due_amount = bill.grand_total

    return bill


# router.py
from app.accounts.bill.service import InvoiceService



@router.post(
    "/{bill_id}/add-item",
    response_model=EditBillResponse
)
async def add_bill_item(
    bill_id: int,
    data: AddBillItemRequest,
    db: SessionDep
):
    # ============================================
    # BILL
    # ============================================

    bill = await db.get(Bill, bill_id)

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # ============================================
    # COMPLETE BILL CANNOT BE MODIFIED
    # ============================================

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Completed bill cannot be modified"
        )

    # ============================================
    # ORDER
    # ============================================

    order = await db.get(Order, bill.order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # ============================================
    # ITEM
    # ============================================

    menu_item = await db.get(Item, data.item_id)

    if not menu_item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    # ============================================
    # ALREADY EXISTS ?
    # ============================================

    result = await db.execute(
        select(OrderItem).where(
            OrderItem.order_id == order.id,
            OrderItem.item_id == data.item_id
        )
    )

    order_item = result.scalar_one_or_none()

    # ============================================
    # PRICING
    # ============================================

    pricing_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == data.item_id,
            Pricing.client_id == bill.client_id,
            Pricing.branch_id == bill.branch_id,
            Pricing.is_active == True
        )
    )

    pricing = pricing_result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(
            status_code=404,
            detail="Pricing not found"
        )

    unit_price = float(pricing.price or 0)
    discount_percent = float(pricing.discount or 0)
    tax_percent = float(pricing.tax or 0)

    discounted_price = unit_price - (
        unit_price * discount_percent / 100
    )

    tax_per_unit = discounted_price * tax_percent / 100

    # ============================================
    # UPDATE IF EXISTS
    # ============================================

    if order_item:

        order_item.quantity += data.quantity

        order_item.subtotal = round(
            discounted_price * order_item.quantity,
            2
        )

        order_item.tax_amount = round(
            tax_per_unit * order_item.quantity,
            2
        )

        order_item.total_price = round(
            order_item.subtotal +
            order_item.tax_amount,
            2
        )

    else:

        subtotal = round(
            discounted_price * data.quantity,
            2
        )

        tax_amount = round(
            tax_per_unit * data.quantity,
            2
        )

        total_price = round(
            subtotal + tax_amount,
            2
        )

        db.add(
            OrderItem(
                order_id=order.id,
                item_id=data.item_id,
                quantity=data.quantity,
                unit_price=unit_price,
                discount_percent=discount_percent,
                tax_percent=tax_percent,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_price=total_price,
                # BUG #3b FIX: Mark new items as "served" so the frontend
                # order-level served filter does not hide the bill after add.
                order_status="served",
            )
        )

    await db.flush()

    # ============================================
    # RECALCULATE BILL
    # ============================================

    result = await db.execute(
        select(OrderItem).where(
            OrderItem.order_id == order.id
        )
    )

    order_items = result.scalars().all()

    subtotal = round(
        sum(float(i.subtotal or 0) for i in order_items),
        2
    )

    tax_total = round(
        sum(float(i.tax_amount or 0) for i in order_items),
        2
    )

    cgst = round(tax_total / 2, 2)
    sgst = round(tax_total / 2, 2)

    service_charge = round(
        subtotal *
        (bill.service_charge_percent / 100),
        2
    )

    grand_total = round(
        subtotal +
        tax_total +
        service_charge,
        2
    )

    # ============================================
    # APPLY EXISTING OFFER AGAIN
    # ============================================

    offer_discount = 0
    final_amount = grand_total

    if bill.offer_id:

        offer = await db.get(
            Offer,
            bill.offer_id
        )

        if offer:

            if offer.offer_type == OfferType.FLAT_DISCOUNT:

                offer_discount = min(
                    float(offer.discount_value or 0),
                    grand_total
                )

            elif offer.offer_type == OfferType.PERCENTAGE_OFF:

                offer_discount = round(
                    grand_total *
                    (offer.discount_value / 100),
                    2
                )

            final_amount = round(
                grand_total - offer_discount,
                2
            )

    # ============================================
    # UPDATE BILL
    # ============================================

    order.total_amount = final_amount

    bill.subtotal = subtotal
    bill.tax_total = tax_total
    bill.cgst_amount = cgst
    bill.sgst_amount = sgst
    bill.service_charge_amount = service_charge
    bill.grand_total = grand_total
    bill.offer_discount = offer_discount
    bill.final_amount = final_amount
    bill.due_amount = final_amount
    bill.is_edited = True

    if bill.payment_status != PaymentStatus.pending:
        bill.payment_status = PaymentStatus.edited

    await db.commit()
    await db.refresh(bill)

    # ============================================
    # CLEAR CACHE
    # ============================================

    await Cache.delete(f"invoice:pdf:{bill.id}")
    await Cache.delete_pattern(
        f"dashboard:*:branch:{bill.branch_id}"
    )

    return bill