# from uuid import uuid4
# from datetime import datetime
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from fastapi import APIRouter, Depends, HTTPException, Response
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session
# from io import BytesIO
# from app.accounts.branch.model import Branch
# from app.accounts.crm.customer_history.checkout_service import handle_customer_and_visit

# from app.db.config import get_db
# from app.accounts.bill.service import InvoiceService, _calculate_offer_discount
# from app.accounts.deps import get_current_user, UserRole
# from app.db.config import SessionDep
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.accounts.order.model import (
#     Order,
#     OrderItem
# )
# from app.accounts.bill.enum import PaymentStatus

# from app.accounts.tax.model import TaxBillingSetting

# from app.accounts.bill.model import Bill
# from app.accounts.offer.model import Offer, OfferType
# from app.accounts.bill.schema import AddBillItemRequest, BillOut, EditBillItemsRequest, EditBillResponse, OfferPreviewRequest, OfferPreviewResponse, BillStatusUpdate, BillStatusResponse

# from app.accounts.pricing.model import Pricing

# from app.accounts.table.model import Table
# from app.accounts.table.schema import TableStatus
# from app.core.cache import Cache

# router = APIRouter(
#     prefix="/bill",
#     tags=["Bill"]
# )


# # =========================================================
# # SERVICE CHARGE HELPERS
# # =========================================================

# def _service_charge_rate(
#     tax: TaxBillingSetting
# ) -> float:
#     return float(
#         tax.service_charge or 0.0
#     )


# def _compute_service_charge(
#     tax: TaxBillingSetting,
#     subtotal: float,
# ) -> tuple[float, float]:
#     percent = _service_charge_rate(tax)

#     if percent <= 0:
#         return 0.0, 0.0

#     return (
#         percent,
#         round(
#             subtotal * (percent / 100),
#             2
#         )
#     )


# # =========================================================
# # GET BILL
# # =========================================================

# @router.get(
#     "/{order_id}",
#     response_model=BillOut,
# )
# async def get_bill(
#     order_id: int,
#     db: SessionDep,
# ):
#     # =====================================================
#     # GET ORDER
#     # =====================================================

#     result = await db.execute(
#         select(Order)
#         .options(
#             selectinload(Order.order_items)
#             .selectinload(OrderItem.item)
#         )
#         .where(
#             Order.id == order_id
#         )
#     )

#     order = result.scalar_one_or_none()

#     if not order:
#         raise HTTPException(
#             status_code=404,
#             detail="Order not found",
#         )

#     # =====================================================
#     # TAX SETTINGS
#     # =====================================================

#     tax_result = await db.execute(
#         select(TaxBillingSetting)
#         .where(
#             TaxBillingSetting.branch_id
#             == order.branch_id
#         )
#     )

#     tax = tax_result.scalar_one_or_none()

#     if not tax:
#         raise HTTPException(
#             status_code=404,
#             detail="Tax settings not found",
#         )

#     # =====================================================
#     # INITIALIZE
#     # =====================================================

#     items = []
#     subtotal = 0.0

#     # =====================================================
#     # ORDER ITEMS
#     # =====================================================

#     item_ids = [
#         oi.item_id
#         for oi in order.order_items
#         if oi.item_id
#     ]

#     pricing_map = {}

#     if item_ids:

#         pricing_result = await db.execute(
#             select(Pricing)
#             .where(
#                 Pricing.item_id.in_(item_ids),
#                 Pricing.client_id
#                 == order.client_id,
#                 Pricing.branch_id
#                 == order.branch_id,
#                 Pricing.is_active == True,
#             )
#         )

#         for pricing in pricing_result.scalars().all():

#             pricing_map.setdefault(
#                 pricing.item_id,
#                 []
#             ).append(
#                 pricing
#             )

#     for order_item in order.order_items:

#         # -------------------------------------------------
#         # IMPORTANT:
#         # Use actual order-item subtotal.
#         # Do NOT recalculate from current pricing.
#         # -------------------------------------------------

#         item_subtotal = (
#             float(
#                 order_item.subtotal
#                 or 0
#             )
#         )

#         if item_subtotal <= 0:

#             item_subtotal = round(
#                 float(
#                     order_item.price or
#                     order_item.unit_price or
#                     0
#                 )
#                 * int(
#                     order_item.quantity or 0
#                 ),
#                 2,
#             )

#         subtotal += item_subtotal

#         item = order_item.item

#         if not item:
#             continue

#         # -------------------------------------------------
#         # PRICING RESPONSE
#         # -------------------------------------------------

#         pricing_list = []

#         for pricing in pricing_map.get(
#             item.id,
#             [],
#         ):

#             price = float(
#                 pricing.price or 0
#             )

#             discount = float(
#                 pricing.discount or 0
#             )

#             # Existing project convention:
#             # pricing.discount is percentage.
#             discounted_price = round(
#                 price
#                 - (
#                     price
#                     * discount
#                     / 100
#                 ),
#                 2,
#             )

#             cgst_rate = float(
#                 pricing.cgst_rate or 0
#             )

#             sgst_rate = float(
#                 pricing.sgst_rate or 0
#             )

#             cgst_amount = round(
#                 discounted_price
#                 * cgst_rate
#                 / 100,
#                 2,
#             )

#             sgst_amount = round(
#                 discounted_price
#                 * sgst_rate
#                 / 100,
#                 2,
#             )

#             total_tax_amount = round(
#                 cgst_amount
#                 + sgst_amount,
#                 2,
#             )

#             total_price = round(
#                 discounted_price
#                 + total_tax_amount,
#                 2,
#             )

#             pricing_list.append({
#                 "id": pricing.id,
#                 "client_id": pricing.client_id,
#                 "branch_id": pricing.branch_id,
#                 "item_id": pricing.item_id,
#                 "price": price,
#                 "cost_price": pricing.cost_price,
#                 "discount": pricing.discount,
#                 "tax": pricing.tax,
#                 "calories": pricing.calories,
#                 "is_active": pricing.is_active,
#                 "created_at": pricing.created_at,
#                 "cgst_rate": cgst_rate,
#                 "sgst_rate": sgst_rate,
#                 "discounted_price": discounted_price,
#                 "cgst_amount": cgst_amount,
#                 "sgst_amount": sgst_amount,
#                 "total_tax_amount": total_tax_amount,
#                 "total_price": total_price,
#             })

#         items.append({
#             "id": item.id,
#             "name": item.name,
#             "client_id": item.client_id,
#             "category_id": item.category_id,
#             "branch_id": item.branch_id,
#             "created_at": item.created_at,
#             "is_active": item.is_active,
#             "pricings": pricing_list,
#         })

#     subtotal = round(
#         subtotal,
#         2,
#     )

#     # =====================================================
#     # TAX
#     # =====================================================

#     cgst_amount = 0.0
#     sgst_amount = 0.0

#     if tax.enable_tax:

#         cgst_amount = round(
#             subtotal
#             * float(tax.cgst or 0)
#             / 100,
#             2,
#         )

#         sgst_amount = round(
#             subtotal
#             * float(tax.sgst or 0)
#             / 100,
#             2,
#         )

#     tax_total = round(
#         cgst_amount
#         + sgst_amount,
#         2,
#     )

#     # =====================================================
#     # SERVICE CHARGE
#     # =====================================================

#     service_charge_percent = float(
#         tax.service_charge or 0
#     )

#     service_charge_amount = round(
#         subtotal
#         * service_charge_percent
#         / 100,
#         2,
#     )

#     # =====================================================
#     # BILL
#     # =====================================================

#     bill_result = await db.execute(
#         select(Bill)
#         .where(
#             Bill.order_id == order.id
#         )
#     )

#     bill = bill_result.scalar_one_or_none()

#     # =====================================================
#     # CREATE BILL
#     # =====================================================

#     if not bill:

#         calculated = _calculate_bill_totals(
#             subtotal=subtotal,
#             tax_total=tax_total,
#             service_charge_percent=
#                 service_charge_percent,
#             discount_amount=0.0,
#             offer_discount=0.0,
#             round_off_enabled=
#                 bool(tax.round_off_bill),
#         )

#         bill = Bill(
#             order_id=order.id,
#             client_id=order.client_id,
#             branch_id=order.branch_id,

#             invoice_no=(
#                 f"INV-{uuid4().hex[:8].upper()}"
#             ),

#             order_type=order.order_type,

#             customer_name=order.customer_name,
#             customer_phone=order.customer_phone,

#             payment_status=
#                 PaymentStatus.pending,

#             payment_method=None,

#             subtotal=subtotal,

#             cgst_percent=(
#                 float(tax.cgst or 0)
#                 if tax.enable_tax
#                 else 0.0
#             ),

#             cgst_amount=cgst_amount,

#             sgst_percent=(
#                 float(tax.sgst or 0)
#                 if tax.enable_tax
#                 else 0.0
#             ),

#             sgst_amount=sgst_amount,

#             service_charge_percent=
#                 service_charge_percent,

#             service_charge_amount=
#                 calculated[
#                     "service_charge_amount"
#                 ],

#             tax_total=tax_total,

#             discount_amount=0.0,

#             round_off_amount=
#                 calculated[
#                     "round_off_amount"
#                 ],

#             grand_total=
#                 calculated[
#                     "grand_total"
#                 ],

#             offer_id=None,

#             offer_discount=0.0,

#             final_amount=
#                 calculated[
#                     "final_amount"
#                 ],

#             paid_amount=0.0,

#             due_amount=
#                 calculated[
#                     "final_amount"
#                 ],

#             footer_message=
#                 tax.bill_footer_message,
#         )

#         db.add(bill)

#         await db.commit()
#         await db.refresh(bill)

#         await Cache.delete_pattern(
#             f"dashboard:*:branch:{order.branch_id}"
#         )

#     else:

#         # =================================================
#         # DO NOT RECALCULATE COMPLETED BILLS
#         # =================================================

#         if bill.payment_status != PaymentStatus.complete:

#             offer_discount = float(
#                 bill.offer_discount or 0
#             )

#             calculated = _calculate_bill_totals(
#                 subtotal=subtotal,
#                 tax_total=tax_total,
#                 service_charge_percent=
#                     service_charge_percent,
#                 discount_amount=
#                     float(
#                         bill.discount_amount or 0
#                     ),
#                 offer_discount=
#                     offer_discount,
#                 round_off_enabled=
#                     bool(tax.round_off_bill),
#             )

#             bill.subtotal = subtotal
#             bill.cgst_percent = (
#                 float(tax.cgst or 0)
#                 if tax.enable_tax
#                 else 0.0
#             )
#             bill.cgst_amount = cgst_amount

#             bill.sgst_percent = (
#                 float(tax.sgst or 0)
#                 if tax.enable_tax
#                 else 0.0
#             )
#             bill.sgst_amount = sgst_amount

#             bill.tax_total = tax_total

#             bill.service_charge_percent = (
#                 service_charge_percent
#             )

#             bill.service_charge_amount = (
#                 calculated[
#                     "service_charge_amount"
#                 ]
#             )

#             bill.round_off_amount = (
#                 calculated[
#                     "round_off_amount"
#                 ]
#             )

#             bill.grand_total = (
#                 calculated[
#                     "grand_total"
#                 ]
#             )

#             bill.final_amount = (
#                 calculated[
#                     "final_amount"
#                 ]
#             )

#             bill.due_amount = max(
#                 round(
#                     bill.final_amount
#                     - float(
#                         bill.paid_amount or 0
#                     ),
#                     2,
#                 ),
#                 0.0,
#             )

#             await db.commit()
#             await db.refresh(bill)

#     # =====================================================
#     # RESPONSE
#     # =====================================================

#     return {
#         "id": bill.id,
#         "order_id": bill.order_id,
#         "branch_id": bill.branch_id,

#         "invoice_no": bill.invoice_no,
#         "order_type": bill.order_type,

#         "customer_name": bill.customer_name,
#         "customer_phone": bill.customer_phone,

#         "table_id": order.table_id,

#         "payment_status":
#             bill.payment_status,

#         "payment_method":
#             bill.payment_method,

#         "created_at":
#             bill.created_at,

#         "items": items,

#         "subtotal":
#             bill.subtotal,

#         "cgst_percent":
#             bill.cgst_percent,

#         "cgst_amount":
#             bill.cgst_amount,

#         "sgst_percent":
#             bill.sgst_percent,

#         "sgst_amount":
#             bill.sgst_amount,

#         "service_charge_percent":
#             bill.service_charge_percent,

#         "service_charge_amount":
#             bill.service_charge_amount,

#         "tax_total":
#             bill.tax_total,

#         "discount_amount":
#             bill.discount_amount,

#         "round_off_amount":
#             bill.round_off_amount,

#         "grand_total":
#             bill.grand_total,

#         "paid_amount":
#             bill.paid_amount,

#         "due_amount":
#             bill.due_amount,

#         "footer_message":
#             bill.footer_message or "",

#         "offer_id":
#             bill.offer_id,

#         "offer_discount":
#             bill.offer_discount or 0.0,

#         "final_amount":
#             bill.final_amount,

#         "is_edited":
#             bill.is_edited,
#     }

# # =========================================================
# # OFFER PREVIEW — POST /bill/offer-preview
# # Returns a discount preview without persisting anything.
# # =========================================================

# # @router.post(
# #     "/offer-preview",
# #     response_model=OfferPreviewResponse
# # )
# # async def offer_preview(
# #     data: OfferPreviewRequest,
# #     db: SessionDep
# # ):
# #     # --------------------------------------------------
# #     # 1. Fetch Bill
# #     # --------------------------------------------------
# #     bill_result = await db.execute(
# #         select(Bill).where(Bill.id == data.bill_id)
# #     )
# #     bill = bill_result.scalar_one_or_none()

# #     if not bill:
# #         raise HTTPException(status_code=404, detail="Bill not found")

# #     grand_total = float(bill.grand_total or 0)
# #     paid_amount = float(bill.paid_amount or 0)

# #     offer_discount = 0.0
# #     message = None

# #     # --------------------------------------------------
# #     # 2. Calculate Offer Discount (if offer_id provided)
# #     # --------------------------------------------------
# #     if data.offer_id is not None:
# #         offer_result = await db.execute(
# #             select(Offer).where(Offer.id == data.offer_id)
# #         )
# #         offer = offer_result.scalar_one_or_none()

# #         if not offer:
# #             raise HTTPException(status_code=404, detail="Offer not found")

# #         if not offer.is_active:
# #             raise HTTPException(status_code=400, detail="Offer is not active")

# #         now = datetime.utcnow()
# #         if offer.valid_from and now < offer.valid_from:
# #             raise HTTPException(status_code=400, detail="Offer has not started yet")
# #         if offer.valid_to and now > offer.valid_to:
# #             raise HTTPException(status_code=400, detail="Offer has expired")

# #         if offer.min_order_amount and grand_total < offer.min_order_amount:
# #             raise HTTPException(
# #                 status_code=400,
# #                 detail=f"Minimum order amount ₹{offer.min_order_amount:.2f} not met"
# #             )

# #         if offer.offer_type == OfferType.FLAT_DISCOUNT:
# #             offer_discount = min(float(offer.discount_value or 0), grand_total)

# #         elif offer.offer_type == OfferType.PERCENTAGE_OFF:
# #             offer_discount = round(grand_total * (float(offer.discount_value or 0) / 100), 2)

# #         # BUY_ONE_GET_ONE / FREE_ITEM — no numeric discount in preview
# #         else:
# #             offer_discount = 0.0
# #             message = f"Offer '{offer.offer_name}' applied — discount calculated at checkout"

# #         message = message or f"Offer '{offer.offer_name}' applied"

# #     final_amount = round(grand_total - offer_discount, 2)
# #     due_amount = round(max(final_amount - paid_amount, 0), 2)

# #     return OfferPreviewResponse(
# #         original_amount=grand_total,
# #         offer_discount=offer_discount,
# #         final_amount=final_amount,
# #         due_amount=due_amount,
# #         message=message,
# #     )




from uuid import uuid4
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.accounts.bill.enum import PaymentStatus
from app.accounts.bill.model import Bill
from app.accounts.bill.schema import (
    BillOut,
    BillStatusUpdate,
    BillStatusResponse,
    OfferPreviewResponse,
    OfferPreviewRequest,
    EditBillResponse,
    EditBillItemsRequest,
    AddBillItemRequest,
)
from app.accounts.order.model import Order, OrderItem
from app.accounts.pricing.model import Pricing
from app.accounts.tax.model import TaxBillingSetting
from app.core.cache import Cache
from app.db.config import SessionDep, get_db
from app.accounts.deps import get_current_user, UserRole
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.accounts.bill.service import _calculate_offer_discount
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from app.accounts.branch.model import Branch
from app.accounts.crm.customer_history.checkout_service import handle_customer_and_visit




router = APIRouter(
    prefix="/bill",
    tags=["Bill"]
)

# =========================================================
# BILL TOTAL CALCULATOR
# =========================================================

def _calculate_bill_totals(
    *,
    subtotal: float,
    tax_total: float,
    service_charge_percent: float = 0.0,
    discount_amount: float = 0.0,
    offer_discount: float = 0.0,
    round_off_enabled: bool = False,
) -> dict:

    subtotal = round(float(subtotal or 0), 2)
    tax_total = round(float(tax_total or 0), 2)

    service_charge_percent = round(
        float(service_charge_percent or 0),
        2,
    )

    service_charge_amount = round(
        subtotal * service_charge_percent / 100,
        2,
    )

    discount_amount = round(
        float(discount_amount or 0),
        2,
    )

    offer_discount = round(
        float(offer_discount or 0),
        2,
    )

    # Never allow discount to exceed payable amount.
    total_before_discount = round(
        subtotal
        + tax_total
        + service_charge_amount,
        2,
    )

    total_discount = min(
        discount_amount + offer_discount,
        total_before_discount,
    )

    calculated_total = round(
        total_before_discount - total_discount,
        2,
    )

    # -----------------------------------------------------
    # ROUND OFF
    # -----------------------------------------------------

    if round_off_enabled:
        grand_total = float(round(calculated_total))

        round_off_amount = round(
            grand_total - calculated_total,
            2,
        )
    else:
        grand_total = calculated_total
        round_off_amount = 0.0

    final_amount = round(
        max(grand_total, 0.0),
        2,
    )

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


# =========================================================
# GET BILL
# =========================================================

@router.get(
    "/{order_id}",
    response_model=BillOut,
)
async def get_bill(
    order_id: int,
    db: SessionDep,
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
        .where(
            Order.id == order_id
        )
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # =====================================================
    # GET TAX SETTINGS
    # =====================================================

    tax_result = await db.execute(
        select(TaxBillingSetting)
        .where(
            TaxBillingSetting.branch_id
            == order.branch_id
        )
    )

    tax = tax_result.scalar_one_or_none()

    if not tax:
        raise HTTPException(
            status_code=404,
            detail="Tax settings not found",
        )

    # =====================================================
    # INITIALIZE
    # =====================================================

    items = []
    subtotal = 0.0

    # =====================================================
    # GET PRICING IN ONE QUERY
    # =====================================================

    item_ids = [
        oi.item_id
        for oi in order.order_items
        if oi.item_id
    ]

    pricing_map = {}

    if item_ids:

        pricing_result = await db.execute(
            select(Pricing)
            .where(
                Pricing.item_id.in_(item_ids),
                Pricing.client_id == order.client_id,
                Pricing.branch_id == order.branch_id,
                Pricing.is_active == True,
            )
        )

        for pricing in pricing_result.scalars().all():

            pricing_map.setdefault(
                pricing.item_id,
                [],
            ).append(pricing)

    # =====================================================
    # BUILD ITEMS
    # =====================================================

    for order_item in order.order_items:

        # -------------------------------------------------
        # USE STORED ORDER ITEM VALUES
        # -------------------------------------------------

        item_subtotal = float(
            getattr(
                order_item,
                "subtotal",
                0,
            )
            or 0
        )

        # Backward compatibility for old order items.
        if item_subtotal <= 0:

            unit_price = float(
                getattr(
                    order_item,
                    "unit_price",
                    None,
                )
                or getattr(
                    order_item,
                    "price",
                    0,
                )
                or 0
            )

            quantity = int(
                getattr(
                    order_item,
                    "quantity",
                    0,
                )
                or 0
            )

            item_subtotal = round(
                unit_price * quantity,
                2,
            )

        subtotal += item_subtotal

        item = order_item.item

        if not item:
            continue

        # -------------------------------------------------
        # PRICING RESPONSE
        # -------------------------------------------------

        pricing_list = []

        for pricing in pricing_map.get(
            item.id,
            [],
        ):

            price = float(
                pricing.price or 0
            )

            discount = float(
                pricing.discount or 0
            )

            discounted_price = round(
                price
                - (
                    price
                    * discount
                    / 100
                ),
                2,
            )

            cgst_rate = float(
                pricing.cgst_rate or 0
            )

            sgst_rate = float(
                pricing.sgst_rate or 0
            )

            cgst_amount = round(
                discounted_price
                * cgst_rate
                / 100,
                2,
            )

            sgst_amount = round(
                discounted_price
                * sgst_rate
                / 100,
                2,
            )

            total_tax_amount = round(
                cgst_amount
                + sgst_amount,
                2,
            )

            total_price = round(
                discounted_price
                + total_tax_amount,
                2,
            )

            pricing_list.append({
                "id": pricing.id,
                "client_id": pricing.client_id,
                "branch_id": pricing.branch_id,
                "item_id": pricing.item_id,
                "price": price,
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
                "total_price": total_price,
            })

        items.append({
            "id": item.id,
            "name": item.name,
            "client_id": item.client_id,
            "category_id": item.category_id,
            "branch_id": item.branch_id,
            "created_at": item.created_at,
            "is_active": item.is_active,
            "pricings": pricing_list,
        })

    subtotal = round(
        subtotal,
        2,
    )

    # =====================================================
    # TAX
    # =====================================================

    if tax.enable_tax:

        cgst_percent = float(
            tax.cgst or 0
        )

        sgst_percent = float(
            tax.sgst or 0
        )

        cgst_amount = round(
            subtotal
            * cgst_percent
            / 100,
            2,
        )

        sgst_amount = round(
            subtotal
            * sgst_percent
            / 100,
            2,
        )

    else:

        cgst_percent = 0.0
        sgst_percent = 0.0

        cgst_amount = 0.0
        sgst_amount = 0.0

    tax_total = round(
        cgst_amount
        + sgst_amount,
        2,
    )

    # =====================================================
    # SERVICE CHARGE
    # =====================================================

    service_charge_percent = float(
        tax.service_charge or 0
    )

    # =====================================================
    # GET EXISTING BILL
    # =====================================================

    bill_result = await db.execute(
        select(Bill)
        .where(
            Bill.order_id == order.id
        )
    )

    bill = bill_result.scalar_one_or_none()

    # =====================================================
    # CREATE BILL
    # =====================================================

    if not bill:

        calculated = _calculate_bill_totals(
            subtotal=subtotal,
            tax_total=tax_total,
            service_charge_percent=service_charge_percent,
            discount_amount=0.0,
            offer_discount=0.0,
            round_off_enabled=bool(
                tax.round_off_bill
            ),
        )

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

            payment_status=PaymentStatus.pending,

            payment_method=None,

            subtotal=calculated["subtotal"],

            cgst_percent=cgst_percent,
            cgst_amount=cgst_amount,

            sgst_percent=sgst_percent,
            sgst_amount=sgst_amount,

            service_charge_percent=(
                calculated[
                    "service_charge_percent"
                ]
            ),

            service_charge_amount=(
                calculated[
                    "service_charge_amount"
                ]
            ),

            tax_total=tax_total,

            discount_amount=0.0,

            round_off_amount=(
                calculated[
                    "round_off_amount"
                ]
            ),

            grand_total=(
                calculated[
                    "grand_total"
                ]
            ),

            offer_id=None,

            offer_discount=0.0,

            final_amount=(
                calculated[
                    "final_amount"
                ]
            ),

            paid_amount=0.0,

            due_amount=(
                calculated[
                    "final_amount"
                ]
            ),

            footer_message=(
                tax.bill_footer_message
            ),
        )

        db.add(bill)

        await db.commit()
        await db.refresh(bill)

        await Cache.delete_pattern(
            f"dashboard:*:branch:{order.branch_id}"
        )

    # =====================================================
    # UPDATE EXISTING BILL
    # =====================================================

    else:

        # -------------------------------------------------
        # COMPLETED BILL MUST NEVER BE RECALCULATED HERE.
        # -------------------------------------------------

        if bill.payment_status != PaymentStatus.complete:

            offer_discount = float(
                bill.offer_discount or 0
            )

            discount_amount = float(
                bill.discount_amount or 0
            )

            calculated = _calculate_bill_totals(
                subtotal=subtotal,
                tax_total=tax_total,
                service_charge_percent=(
                    service_charge_percent
                ),
                discount_amount=discount_amount,
                offer_discount=offer_discount,
                round_off_enabled=bool(
                    tax.round_off_bill
                ),
            )

            bill.subtotal = calculated["subtotal"]

            bill.cgst_percent = cgst_percent
            bill.cgst_amount = cgst_amount

            bill.sgst_percent = sgst_percent
            bill.sgst_amount = sgst_amount

            bill.tax_total = calculated["tax_total"]

            bill.service_charge_percent = (
                calculated[
                    "service_charge_percent"
                ]
            )

            bill.service_charge_amount = (
                calculated[
                    "service_charge_amount"
                ]
            )

            bill.discount_amount = (
                discount_amount
            )

            bill.offer_discount = (
                offer_discount
            )

            bill.round_off_amount = (
                calculated[
                    "round_off_amount"
                ]
            )

            bill.grand_total = (
                calculated[
                    "grand_total"
                ]
            )

            bill.final_amount = (
                calculated[
                    "final_amount"
                ]
            )

            paid_amount = float(
                bill.paid_amount or 0
            )

            bill.due_amount = round(
                max(
                    bill.final_amount
                    - paid_amount,
                    0.0,
                ),
                2,
            )

            await db.commit()
            await db.refresh(bill)

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

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

        "table_id": (
            order.table_id
        ),

        "payment_status": (
            bill.payment_status
        ),

        "payment_method": (
            bill.payment_method
        ),

        "created_at": (
            bill.created_at
        ),

        "items": items,

        "subtotal": float(
            bill.subtotal or 0
        ),

        "cgst_percent": float(
            bill.cgst_percent or 0
        ),

        "cgst_amount": float(
            bill.cgst_amount or 0
        ),

        "sgst_percent": float(
            bill.sgst_percent or 0
        ),

        "sgst_amount": float(
            bill.sgst_amount or 0
        ),

        "service_charge_percent": float(
            bill.service_charge_percent or 0
        ),

        "service_charge_amount": float(
            bill.service_charge_amount or 0
        ),

        "tax_total": float(
            bill.tax_total or 0
        ),

        "discount_amount": float(
            bill.discount_amount or 0
        ),

        "round_off_amount": float(
            bill.round_off_amount or 0
        ),

        "grand_total": float(
            bill.grand_total or 0
        ),

        "paid_amount": float(
            bill.paid_amount or 0
        ),

        "due_amount": float(
            bill.due_amount or 0
        ),

        "footer_message": (
            bill.footer_message or ""
        ),

        "offer_id": bill.offer_id,

        "offer_discount": float(
            bill.offer_discount or 0
        ),

        "final_amount": (
            float(bill.final_amount)
            if bill.final_amount is not None
            else None
        ),

        "is_edited": bool(
            bill.is_edited
        ),
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
    print("HANDLE CUSTOMER CALLED")####################################
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
    # NOTE: Ye guard hi customer/visit-history creation ko
    # idempotent banata hai — complete/cancel ho chuke bill
    # ke liye function dobara chalega hi nahi.

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

    if data.payment_status == PaymentStatus.complete:
        bill.payment_status = PaymentStatus.complete
        bill.paid_amount = (
            bill.final_amount
            if bill.final_amount > 0
            else bill.grand_total
        )
        bill.due_amount = 0.0

        # ==========================================
        # CUSTOMER IDENTIFICATION + VISIT HISTORY
        # Sirf tab trigger hoga jab payment COMPLETE
        # ho rahi hai — yahi asli "successful checkout"
        # moment hai (guard upar isko idempotent bana
        # chuka hai).
        # ==========================================

        branch = await db.get(Branch, bill.branch_id)

        customer = await handle_customer_and_visit(
            db=db,
            client_id=bill.client_id,
            branch_id=bill.branch_id,
            branch_name=branch.name if branch else "",
            order_id=bill.order_id,
            bill_id=bill.id,
            total_amount=bill.final_amount or bill.grand_total,
            discount=(bill.discount_amount or 0) + (bill.offer_discount or 0),
            tax=bill.tax_total or 0,
            payment_method=bill.payment_method,
            table_name=(table.name if order and order.table_id and table else None),
            visit_type=bill.order_type,
            customer_name=bill.customer_name,
            customer_phone=bill.customer_phone,
        )

        # Bill ko bhi identified customer se link karo,
        # taaki future queries (order history, CRM) mein
        # bill -> customer trace ho sake.
        print("RETURNED CUSTOMER =", customer)
        if customer:
            bill.customer_id = customer.id

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

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(bill)

    # Invalidate dashboard cache (payment completed / bill status changed)
    await Cache.delete_pattern(f"dashboard:*:branch:{bill.branch_id}")

    # Invalidate invoice PDF cache since bill status changed
    await Cache.delete(f"invoice:pdf:{bill.id}")

    print("====== PAYMENT COMPLETE ======")
    print("Bill ID:", bill.id)
    print("Customer Name:", bill.customer_name)
    print("Customer Phone:", bill.customer_phone)

    if data.payment_status == PaymentStatus.complete:
        try:
            from app.accounts.crm.events.publisher import crm_event_publisher
            await crm_event_publisher.publish_bill_completed(
                bill_id=bill.id,
                order_id=bill.order_id,
                customer_id=bill.customer_id or 0,
                client_id=bill.client_id,
                branch_id=bill.branch_id
            )
        except Exception as err:
            print("[CRM Event Publisher Error]:", err)

    return bill





# =====================================================
# OFFER PREVIEW ENDPOINT - NO DB UPDATES!
# =====================================================

@router.post(
    "/offer-preview",
    response_model=OfferPreviewResponse,
)
async def offer_preview(
    data: OfferPreviewRequest,
    db: SessionDep,
):
    # =====================================================
    # BILL
    # =====================================================

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == data.bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    original_amount = float(
        bill.grand_total or 0
    )

    # =====================================================
    # NO OFFER
    # =====================================================

    if data.offer_id is None:

        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=max(
                original_amount
                - float(
                    bill.paid_amount or 0
                ),
                0,
            ),
            message="Offer removed",
        )

    # =====================================================
    # OFFER
    # =====================================================

    offer_result = await db.execute(
        select(Offer)
        .where(
            Offer.id == data.offer_id
        )
    )

    offer = offer_result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=404,
            detail="Offer not found",
        )

    if not offer.is_active:

        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
            message="Offer is not active",
        )

    now = datetime.utcnow()

    if (
        offer.valid_from
        and now < offer.valid_from
    ):
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
            message="Offer has not started yet",
        )

    if (
        offer.valid_to
        and now > offer.valid_to
    ):
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
            message="Offer has expired",
        )

    if (
        offer.min_order_amount
        and original_amount
        < float(
            offer.min_order_amount
        )
    ):
        return OfferPreviewResponse(
            original_amount=original_amount,
            offer_discount=0.0,
            final_amount=original_amount,
            due_amount=original_amount,
            message=(
                f"Minimum order amount "
                f"₹{float(offer.min_order_amount):.2f} "
                f"required"
            ),
        )

    # =====================================================
    # DISCOUNT
    # =====================================================

    discount = _calculate_offer_discount(
        offer,
        original_amount,
    )

    final_amount = round(
        max(
            original_amount - discount,
            0,
        ),
        2,
    )

    due_amount = round(
        max(
            final_amount
            - float(
                bill.paid_amount or 0
            ),
            0,
        ),
        2,
    )

    if offer.offer_type in (
        OfferType.BUY_ONE_GET_ONE,
        OfferType.FREE_ITEM,
    ):
        message = (
            f"Offer '{offer.offer_name}' "
            "requires item-level processing"
        )
    else:
        message = (
            f"Offer '{offer.offer_name}' applied"
        )

    return OfferPreviewResponse(
        original_amount=original_amount,
        offer_discount=discount,
        final_amount=final_amount,
        due_amount=due_amount,
        message=message,
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
    response_model=EditBillResponse,
)
async def edit_bill_items(
    bill_id: int,
    data: EditBillItemsRequest,
    db: SessionDep,
):
    # =====================================================
    # BILL
    # =====================================================

    bill = await db.get(
        Bill,
        bill_id,
    )

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Completed bills cannot be edited",
        )

    # =====================================================
    # ORDER
    # =====================================================

    order = await db.get(
        Order,
        bill.order_id,
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # =====================================================
    # PROCESS ITEMS
    # =====================================================

    for item_data in data.items:

        result = await db.execute(
            select(OrderItem)
            .where(
                OrderItem.order_id
                == order.id,
                OrderItem.item_id
                == item_data.item_id,
            )
        )

        order_item = (
            result.scalar_one_or_none()
        )

        # =================================================
        # DELETE
        # =================================================

        if item_data.quantity == 0:

            if order_item:
                await db.delete(
                    order_item
                )

            continue

        # =================================================
        # PRICING
        # =================================================

        pricing_result = await db.execute(
            select(Pricing)
            .where(
                Pricing.item_id
                == item_data.item_id,
                Pricing.client_id
                == bill.client_id,
                Pricing.branch_id
                == bill.branch_id,
                Pricing.is_active == True,
            )
        )

        pricing = (
            pricing_result
            .scalars()
            .first()
        )

        if not pricing:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Pricing not found "
                    f"for item "
                    f"{item_data.item_id}"
                ),
            )

        unit_price = float(
            pricing.price or 0
        )

        discount_percent = float(
            pricing.discount or 0
        )

        tax_percent = float(
            pricing.tax or 0
        )

        discounted_unit_price = round(
            unit_price
            - (
                unit_price
                * discount_percent
                / 100
            ),
            2,
        )

        item_subtotal = round(
            discounted_unit_price
            * item_data.quantity,
            2,
        )

        item_tax = round(
            item_subtotal
            * tax_percent
            / 100,
            2,
        )

        item_total = round(
            item_subtotal
            + item_tax,
            2,
        )

        # =================================================
        # UPDATE
        # =================================================

        if order_item:

            order_item.quantity = (
                item_data.quantity
            )

            order_item.unit_price = (
                unit_price
            )

            order_item.discount_percent = (
                discount_percent
            )

            order_item.tax_percent = (
                tax_percent
            )

            order_item.subtotal = (
                item_subtotal
            )

            order_item.tax_amount = (
                item_tax
            )

            order_item.total_price = (
                item_total
            )

        # =================================================
        # ADD
        # =================================================

        else:

            db.add(
                OrderItem(
                    order_id=order.id,
                    item_id=item_data.item_id,
                    quantity=item_data.quantity,
                    unit_price=unit_price,
                    discount_percent=discount_percent,
                    tax_percent=tax_percent,
                    subtotal=item_subtotal,
                    tax_amount=item_tax,
                    total_price=item_total,
                    order_status="served",
                )
            )

    await db.flush()

    # =====================================================
    # RELOAD
    # =====================================================

    result = await db.execute(
        select(OrderItem)
        .where(
            OrderItem.order_id
            == order.id
        )
    )

    order_items = result.scalars().all()

    if not order_items:
        raise HTTPException(
            status_code=400,
            detail=(
                "Order must contain "
                "at least one item"
            ),
        )

    # =====================================================
    # CALCULATE
    # =====================================================

    subtotal = round(
        sum(
            float(
                item.subtotal or 0
            )
            for item in order_items
        ),
        2,
    )

    tax_total = round(
        sum(
            float(
                item.tax_amount or 0
            )
            for item in order_items
        ),
        2,
    )

    cgst_amount = round(
        tax_total / 2,
        2,
    )

    sgst_amount = round(
        tax_total / 2,
        2,
    )

    service_charge_percent = float(
        bill.service_charge_percent or 0
    )

    service_charge_amount = round(
        subtotal
        * service_charge_percent
        / 100,
        2,
    )

    before_offer = round(
        subtotal
        + tax_total
        + service_charge_amount
        - float(
            bill.discount_amount or 0
        ),
        2,
    )

    # =====================================================
    # ROUND OFF
    # =====================================================

    rounded_total = round(
        before_offer
    )

    round_off_amount = round(
        rounded_total
        - before_offer,
        2,
    )

    grand_total = rounded_total

    # =====================================================
    # OFFER
    # =====================================================

    offer_discount = 0.0

    if bill.offer_id:

        offer = await db.get(
            Offer,
            bill.offer_id,
        )

        if offer:

            offer_discount = (
                _calculate_offer_discount(
                    offer,
                    grand_total,
                )
            )

    final_amount = round(
        max(
            grand_total
            - offer_discount,
            0,
        ),
        2,
    )

    # =====================================================
    # UPDATE BILL
    # =====================================================

    bill.subtotal = subtotal

    bill.cgst_amount = (
        cgst_amount
    )

    bill.sgst_amount = (
        sgst_amount
    )

    bill.tax_total = (
        tax_total
    )

    bill.service_charge_amount = (
        service_charge_amount
    )

    bill.round_off_amount = (
        round_off_amount
    )

    bill.grand_total = (
        grand_total
    )

    bill.offer_discount = (
        offer_discount
    )

    bill.final_amount = (
        final_amount
    )

    bill.paid_amount = 0.0

    bill.due_amount = (
        final_amount
    )

    bill.is_edited = True

    bill.payment_status = (
        PaymentStatus.edited
    )

    # Order total should represent customer payable amount
    order.total_amount = (
        final_amount
    )

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()
    await db.refresh(bill)

    # =====================================================
    # CACHE
    # =====================================================

    await Cache.delete(
        f"invoice:pdf:{bill.id}"
    )

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
        client_id = getattr(
            user,
            "client_id",
            None,
        )

        branch_id = getattr(
            user,
            "branch_id",
            None,
        )

    elif role == UserRole.CLIENT:
        client_id = user.id

    # =====================================================
    # CACHE
    # =====================================================

    cache_key = f"invoice:pdf:{bill_id}"

    cached_b64 = await Cache.get(
        cache_key
    )

    if cached_b64:

        pdf_bytes = base64.b64decode(
            cached_b64
        )

        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="INV-{bill_id}.pdf"'
            },
        )

    # =====================================================
    # GET BILL
    # =====================================================

    bill = await get_bill_for_invoice(
        db=db,
        bill_id=bill_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    # =====================================================
    # GENERATE PDF
    # =====================================================

    pdf = BytesIO()

    InvoiceTemplate.generate(
        pdf,
        bill,
    )

    pdf_bytes = pdf.getvalue()

    # =====================================================
    # CACHE PDF
    # =====================================================

    await Cache.set(
        cache_key,
        base64.b64encode(
            pdf_bytes
        ).decode("utf-8"),
        expire=86400,
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{bill.invoice_no}.pdf"'
        },
    )





async def get_bill_for_invoice(
    db: AsyncSession,
    bill_id: int,
    client_id: int = None,
    branch_id: int = None,
):
    query = (
        select(Bill)
        .options(
            selectinload(Bill.branch),
            selectinload(Bill.order)
            .selectinload(Order.order_items)
            .selectinload(OrderItem.item),
        )
    )

    conditions = [
        Bill.id == bill_id
    ]

    if client_id is not None:
        conditions.append(
            Bill.client_id == client_id
        )

    if branch_id is not None:
        conditions.append(
            Bill.branch_id == branch_id
        )

    result = await db.execute(
        query.where(*conditions)
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    return bill



# router.py
from app.accounts.bill.service import InvoiceService



@router.post(
    "/{bill_id}/add-item",
    response_model=EditBillResponse,
)
async def add_bill_item(
    bill_id: int,
    data: AddBillItemRequest,
    db: SessionDep,
):
    # =====================================================
    # BILL
    # =====================================================

    bill = await db.get(
        Bill,
        bill_id,
    )

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    if bill.payment_status == PaymentStatus.complete:
        raise HTTPException(
            status_code=400,
            detail="Completed bill cannot be modified",
        )

    # =====================================================
    # ORDER
    # =====================================================

    order = await db.get(
        Order,
        bill.order_id,
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # =====================================================
    # ITEM
    # =====================================================

    item = await db.get(
        Item,
        data.item_id,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    # =====================================================
    # PRICING
    # =====================================================

    pricing_result = await db.execute(
        select(Pricing)
        .where(
            Pricing.item_id
            == data.item_id,
            Pricing.client_id
            == bill.client_id,
            Pricing.branch_id
            == bill.branch_id,
            Pricing.is_active == True,
        )
    )

    pricing = (
        pricing_result
        .scalars()
        .first()
    )

    if not pricing:
        raise HTTPException(
            status_code=404,
            detail="Pricing not found",
        )

    unit_price = float(
        pricing.price or 0
    )

    discount_percent = float(
        pricing.discount or 0
    )

    tax_percent = float(
        pricing.tax or 0
    )

    discounted_unit_price = round(
        unit_price
        - (
            unit_price
            * discount_percent
            / 100
        ),
        2,
    )

    # =====================================================
    # EXISTING ITEM
    # =====================================================

    result = await db.execute(
        select(OrderItem)
        .where(
            OrderItem.order_id
            == order.id,
            OrderItem.item_id
            == data.item_id,
        )
    )

    order_item = (
        result.scalar_one_or_none()
    )

    if order_item:

        order_item.quantity += (
            data.quantity
        )

        quantity = (
            order_item.quantity
        )

    else:

        quantity = data.quantity

        order_item = OrderItem(
            order_id=order.id,
            item_id=data.item_id,
            quantity=quantity,
            unit_price=unit_price,
            discount_percent=discount_percent,
            tax_percent=tax_percent,
            order_status="served",
        )

        db.add(order_item)

    # =====================================================
    # CALCULATE ITEM
    # =====================================================

    item_subtotal = round(
        discounted_unit_price
        * quantity,
        2,
    )

    item_tax = round(
        item_subtotal
        * tax_percent
        / 100,
        2,
    )

    item_total = round(
        item_subtotal
        + item_tax,
        2,
    )

    order_item.unit_price = (
        unit_price
    )

    order_item.discount_percent = (
        discount_percent
    )

    order_item.tax_percent = (
        tax_percent
    )

    order_item.subtotal = (
        item_subtotal
    )

    order_item.tax_amount = (
        item_tax
    )

    order_item.total_price = (
        item_total
    )

    await db.flush()

    # =====================================================
    # ALL ITEMS
    # =====================================================

    result = await db.execute(
        select(OrderItem)
        .where(
            OrderItem.order_id
            == order.id
        )
    )

    order_items = (
        result.scalars().all()
    )

    subtotal = round(
        sum(
            float(
                item.subtotal or 0
            )
            for item in order_items
        ),
        2,
    )

    tax_total = round(
        sum(
            float(
                item.tax_amount or 0
            )
            for item in order_items
        ),
        2,
    )

    cgst_amount = round(
        tax_total / 2,
        2,
    )

    sgst_amount = round(
        tax_total / 2,
        2,
    )

    service_charge_amount = round(
        subtotal
        * float(
            bill.service_charge_percent
            or 0
        )
        / 100,
        2,
    )

    before_offer = round(
        subtotal
        + tax_total
        + service_charge_amount
        - float(
            bill.discount_amount or 0
        ),
        2,
    )

    # =====================================================
    # ROUND
    # =====================================================

    grand_total = float(
        round(before_offer)
    )

    round_off_amount = round(
        grand_total
        - before_offer,
        2,
    )

    # =====================================================
    # OFFER
    # =====================================================

    offer_discount = 0.0

    if bill.offer_id:

        offer = await db.get(
            Offer,
            bill.offer_id,
        )

        if offer:

            offer_discount = (
                _calculate_offer_discount(
                    offer,
                    grand_total,
                )
            )

    final_amount = round(
        max(
            grand_total
            - offer_discount,
            0,
        ),
        2,
    )

    # =====================================================
    # BILL
    # =====================================================

    bill.subtotal = subtotal

    bill.cgst_amount = (
        cgst_amount
    )

    bill.sgst_amount = (
        sgst_amount
    )

    bill.tax_total = (
        tax_total
    )

    bill.service_charge_amount = (
        service_charge_amount
    )

    bill.round_off_amount = (
        round_off_amount
    )

    bill.grand_total = (
        grand_total
    )

    bill.offer_discount = (
        offer_discount
    )

    bill.final_amount = (
        final_amount
    )

    bill.paid_amount = 0.0

    bill.due_amount = (
        final_amount
    )

    bill.is_edited = True

    bill.payment_status = (
        PaymentStatus.edited
    )

    order.total_amount = (
        final_amount
    )

    # =====================================================
    # SAVE
    # =====================================================

    await db.commit()
    await db.refresh(bill)

    # =====================================================
    # CACHE
    # =====================================================

    await Cache.delete(
        f"invoice:pdf:{bill.id}"
    )

    await Cache.delete_pattern(
        f"dashboard:*:branch:{bill.branch_id}"
    )

    return bill


@router.patch(
    "/status/{bill_id}",
    response_model=BillStatusResponse,
)
async def update_bill_status(
    bill_id: int,
    data: BillStatusUpdate,
    db: SessionDep,
):
    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(
            status_code=404,
            detail="Bill not found",
        )

    # =====================================================
    # COMPLETED BILL CANNOT BE CHANGED
    # =====================================================

    if (
        bill.payment_status
        == PaymentStatus.complete
        and data.payment_status
        != PaymentStatus.complete
    ):
        raise HTTPException(
            status_code=400,
            detail="Completed bill cannot be modified",
        )

    # =====================================================
    # ORDER
    # =====================================================

    order = await db.get(
        Order,
        bill.order_id,
    )

    table = None

    if order and order.table_id:

        table = await db.get(
            Table,
            order.table_id,
        )

    # =====================================================
    # COMPLETE
    # =====================================================

    if data.payment_status == PaymentStatus.complete:

        bill.payment_status = (
            PaymentStatus.complete
        )

        bill.paid_amount = round(
            float(
                bill.final_amount
                or bill.grand_total
                or 0
            ),
            2,
        )

        bill.due_amount = 0.0

        if table:

            table.status = (
                TableStatus.available
            )

            await Cache.delete(
                f"tables:branch:{table.branch_id}"
            )

        # =================================================
        # CUSTOMER
        # =================================================

        branch = await db.get(
            Branch,
            bill.branch_id,
        )

        customer = await handle_customer_and_visit(
            db=db,
            client_id=bill.client_id,
            branch_id=bill.branch_id,
            branch_name=(
                branch.name
                if branch
                else ""
            ),
            order_id=bill.order_id,
            bill_id=bill.id,
            total_amount=float(
                bill.final_amount
                or bill.grand_total
                or 0
            ),
            discount=(
                float(
                    bill.discount_amount or 0
                )
                +
                float(
                    bill.offer_discount or 0
                )
            ),
            tax=float(
                bill.tax_total or 0
            ),
            payment_method=
                bill.payment_method,
            table_name=(
                table.name
                if table
                else None
            ),
            visit_type=bill.order_type,
            customer_name=bill.customer_name,
            customer_phone=bill.customer_phone,
        )

        if customer:
            bill.customer_id = customer.id

    # =====================================================
    # CANCEL
    # =====================================================

    elif data.payment_status == PaymentStatus.cancel:

        bill.payment_status = (
            PaymentStatus.cancel
        )

        bill.paid_amount = 0.0

        bill.due_amount = round(
            float(
                bill.final_amount
                or bill.grand_total
                or 0
            ),
            2,
        )

        if table:

            table.status = (
                TableStatus.occupied
            )

            await Cache.delete(
                f"tables:branch:{table.branch_id}"
            )

    # =====================================================
    # EDITED
    # =====================================================

    elif data.payment_status == PaymentStatus.edited:

        bill.payment_status = (
            PaymentStatus.edited
        )

        bill.paid_amount = 0.0

        bill.due_amount = round(
            float(
                bill.final_amount
                or bill.grand_total
                or 0
            ),
            2,
        )

        bill.is_edited = True

        if table:

            table.status = (
                TableStatus.occupied
            )

            await Cache.delete(
                f"tables:branch:{table.branch_id}"
            )

    # =====================================================
    # PENDING
    # =====================================================

    elif data.payment_status == PaymentStatus.pending:

        bill.payment_status = (
            PaymentStatus.pending
        )

        bill.paid_amount = 0.0

        bill.due_amount = round(
            float(
                bill.final_amount
                or bill.grand_total
                or 0
            ),
            2,
        )

        if table:

            table.status = (
                TableStatus.occupied
            )

            await Cache.delete(
                f"tables:branch:{table.branch_id}"
            )

    # =====================================================
    # SAVE
    # =====================================================

    try:

        await db.commit()

    except Exception:

        await db.rollback()
        raise

    await db.refresh(bill)

    # =====================================================
    # CACHE
    # =====================================================

    await Cache.delete_pattern(
        f"dashboard:*:branch:{bill.branch_id}"
    )

    await Cache.delete(
        f"invoice:pdf:{bill.id}"
    )

    # =====================================================
    # CRM EVENT
    # =====================================================

    if (
        data.payment_status
        == PaymentStatus.complete
    ):

        try:

            from app.accounts.crm.events.publisher import (
                crm_event_publisher,
            )

            await crm_event_publisher.publish_bill_completed(
                bill_id=bill.id,
                order_id=bill.order_id,
                customer_id=(
                    bill.customer_id or 0
                ),
                client_id=bill.client_id,
                branch_id=bill.branch_id,
            )

        except Exception as err:

            print(
                "[CRM Event Publisher Error]:",
                err,
            )

    return bill