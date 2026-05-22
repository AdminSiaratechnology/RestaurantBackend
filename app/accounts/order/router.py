from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.accounts.client.model import Client
from app.db.config import SessionDep
from app.accounts.deps import access_one, get_client_if_accessible

from app.accounts.item.model import Item
from app.accounts.order.model import Order, OrderItem
from app.accounts.order.schema import OrderCreate, OrderResponse, OrderUpdate
from app.accounts.pricing.model import Pricing


from app.accounts.enum import UserRole


router = APIRouter(prefix="/order", tags=["Order"])


def compute_total_price(pricing: Pricing) -> float:
    """
    Compute per-unit price after applying discount and tax.
    Formula:
      discounted = price - (price × discount% / 100)
      total      = discounted + (discounted × tax_rate% / 100)
    """
    base = pricing.price or 0.0
    disc = pricing.discount or 0.0
    tax  = pricing.tax_rate or 0.0
    discounted = base - (base * disc / 100)
    total = discounted + (discounted * tax / 100)
    return round(total, 2)


def order_item_line_snapshot(pricing: Pricing, quantity: int) -> dict:
    """Build OrderItem column values from a Pricing row."""
    unit_price = pricing.price or 0.0
    discount_percent = pricing.discount or 0.0
    tax_percent = pricing.tax_rate or 0.0
    discounted_unit = unit_price - (unit_price * discount_percent / 100)
    tax_per_unit = discounted_unit * tax_percent / 100
    final_unit = round(discounted_unit + tax_per_unit, 2)
    return {
        "unit_price": round(unit_price, 2),
        "discount_percent": discount_percent,
        "tax_percent": tax_percent,
        "subtotal": round(discounted_unit * quantity, 2),
        "tax_amount": round(tax_per_unit * quantity, 2),
        "total_price": round(final_unit * quantity, 2),
        "line_unit_final": final_unit,
    }


def build_order_item(
    order_id: int,
    item_id: int,
    quantity: int,
    pricing: Pricing,
) -> OrderItem:
    snap = order_item_line_snapshot(pricing, quantity)
    return OrderItem(
        order_id=order_id,
        item_id=item_id,
        quantity=quantity,
        unit_price=snap["unit_price"],
        discount_percent=snap["discount_percent"],
        tax_percent=snap["tax_percent"],
        subtotal=snap["subtotal"],
        tax_amount=snap["tax_amount"],
        total_price=snap["total_price"],
    )


async def resolve_pricing(
    db: SessionDep,
    db_item: Item,
    client_id: int,
    branch_id: int,
) -> Pricing:
    """
    Resolve active pricing: branch-specific first, then any active row for the item.
    If only pricing for another branch exists, clone it for this branch.
    """
    branch_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == db_item.id,
            Pricing.client_id == client_id,
            Pricing.branch_id == branch_id,
            Pricing.is_active == True,
        )
    )
    pricing = branch_result.scalars().first()
    if pricing:
        return pricing

    fallback_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == db_item.id,
            Pricing.client_id == client_id,
            Pricing.is_active == True,
        ).order_by(Pricing.id.desc())
    )
    pricing = fallback_result.scalars().first()
    if pricing:
        if pricing.branch_id == branch_id:
            return pricing
        cloned = Pricing(
            client_id=client_id,
            branch_id=branch_id,
            item_id=db_item.id,
            price=pricing.price,
            cost_price=pricing.cost_price,
            discount=pricing.discount,
            tax_rate=pricing.tax_rate,
            calories=pricing.calories,
            is_active=True,
        )
        db.add(cloned)
        await db.flush()
        return cloned

    template_result = await db.execute(
        select(Pricing).where(
            Pricing.item_id == db_item.id,
            Pricing.client_id == client_id,
        ).order_by(Pricing.id.desc())
    )
    template = template_result.scalars().first()
    if template:
        created = Pricing(
            client_id=client_id,
            branch_id=branch_id,
            item_id=db_item.id,
            price=template.price,
            cost_price=template.cost_price,
            discount=template.discount,
            tax_rate=template.tax_rate,
            calories=template.calories,
            is_active=True,
        )
        db.add(created)
        await db.flush()
        return created

    raise HTTPException(
        400,
        f"No pricing for '{db_item.name}'. Add pricing before placing an order.",
    )

# =========================
# ✅ GET MENU
# =========================

@router.get("/menu")
async def get_menu(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    try:
        role = current["role"]
        user = current["user"]

        # If logged in as staff, enforce their own client and branch to prevent any mismatch or 404
        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id
        else:
            if client_id is None or branch_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="client_id and branch_id are required parameters"
                )

        # ✅ Tenant access
        await get_client_if_accessible(client_id, db, current)

        result = await db.execute(
            select(Item)
            .options(
                selectinload(Item.category),
                selectinload(Item.pricings)
            )
            .where(
                Item.client_id == client_id,
                Item.branch_id == branch_id,
                Item.is_active == True
            )
        )

        items = result.scalars().all()

        menu = {}

        for item in items:

            # ✅ Category Name
            category_name = (
                item.category.name
                if item.category
                else "Others"
            )

            # ✅ Get active pricing for this branch
            pricing = next(
                (
                    p for p in item.pricings
                    if p.branch_id == branch_id and p.is_active
                ),
                None
            )

            if pricing:
                base_price = pricing.price
                total_price = compute_total_price(pricing)
                discount = pricing.discount or 0.0
                tax_rate = pricing.tax_rate or 0.0
            else:
                base_price = 0
                total_price = 0
                discount = 0
                tax_rate = 0

            menu.setdefault(category_name, []).append({
                "id": item.id,
                "name": item.name,
                "price": base_price,
                "discount": discount,
                "tax_rate": tax_rate,
                "total_price": total_price
            })

        return menu

    except HTTPException as e:
        raise e
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error while fetching menu"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    


# =========================
# ✅ GET ALL ORDERS
# =========================
@router.get("/get_all_orders", response_model=list[OrderResponse])
async def get_all_orders(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    try:

        role = current["role"]
        user = current["user"]

        query = (
            select(Order)
            .options(
                selectinload(Order.order_items)
            )
        )

        # ✅ Branch filter
        if branch_id:
            query = query.where(Order.branch_id == branch_id)

        # ✅ Tenant filtering
        if role.name == "CLIENT":
            query = query.where(Order.client_id == user.id)

        elif role.name == "PARTNER":
            query = query.join(
                Client,
                Client.id == Order.client_id
            ).where(
                Client.partner_id == user.id
            )

        # SUPER_ADMIN gets all orders

        result = await db.execute(query)

        orders = result.scalars().all()

        return [
            {
                "id": order.id,
                "client_id": order.client_id,
                "branch_id": order.branch_id,
                "table_id": order.table_id,
                "order_type": order.order_type,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "notes": order.notes,
                "status": order.status,
                "total_amount": order.total_amount,
                "created_at": order.created_at,
                "items": [
                    {
                        "item_id": item.item_id,
                        "quantity": item.quantity,
                        "price": item.price
                    }
                    for item in order.order_items
                ]
            }
            for order in orders
        ]

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error while fetching orders"
        )

# =========================
# ✅ DELETE ORDER
# =========================
# @router.delete("/delete_order/{order_id}")
# async def delete_order(
#     order_id: int,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     try:
#         result = await db.execute(
#             select(Order).where(Order.id == order_id)
#         )
#         order = result.scalar_one_or_none()

#         if not order:
#             raise HTTPException(404, "Order not found")

#         await get_client_if_accessible(order.client_id, db, current)

#         if order.status.lower() != "pending":
#             raise HTTPException(400, "Only pending orders can be deleted")

#         await db.execute(
#             delete(OrderItem).where(OrderItem.order_id == order.id)
#         )

#         await db.delete(order)
#         await db.commit()

#         return {"message": "Order deleted successfully"}

#     except HTTPException as e:
#         await db.rollback()
#         raise e
#     except SQLAlchemyError:
#         await db.rollback()
#         raise HTTPException(500, "Database error while deleting order")

# cancel order_________________-__+___+__+_+_+_+_+_+_+_+_+

@router.patch("/cancel_order/{order_id}")
async def cancel_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    try:
        # ✅ Get order
        result = await db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(404, "Order not found")

        # ✅ Access control
        await get_client_if_accessible(order.client_id, db, current)

        # ✅ Prevent re-cancel or invalid states
        if order.status.lower() == "cancelled":
            raise HTTPException(400, "Order already cancelled")

        if order.status.lower() == "served":
            raise HTTPException(400, "Served orders cannot be cancelled")

        # ✅ Update status instead of delete
        order.status = "cancelled"

        await db.commit()
        await db.refresh(order)

        return {
            "message": "Order cancelled successfully",
            "order_id": order.id,
            "status": order.status
        }

    except HTTPException as e:
        await db.rollback()
        raise e

    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Database error while cancelling order")


# =========================
# ✅ UPDATE ORDER
# =========================
@router.put("/orders_update/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    data: OrderUpdate,
    db: SessionDep,
    current=Depends(access_one)
):
    try:
        # =========================
        # ✅ Fetch Order
        # =========================
        result = await db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(404, "Order not found")

        await get_client_if_accessible(order.client_id, db, current)

        # Enforce branch security for staff on order update
        if current["role"] == UserRole.STAFF and order.branch_id != current["user"].branch_id:
            raise HTTPException(403, "Not allowed to update orders of another branch")

        # =========================
        # ✅ Update Basic Fields
        # =========================
        if data.notes is not None:
            order.notes = data.notes

        if data.order_type is not None:
            order.order_type = data.order_type

        # =========================
        # ✅ Update Items
        # =========================
        if data.items is not None:

            # Delete old items
            await db.execute(
                delete(OrderItem).where(OrderItem.order_id == order.id)
            )

            total = 0

            for item in data.items:

                if item.quantity <= 0:
                    raise HTTPException(
                        400,
                        f"Invalid quantity for item {item.item_id}"
                    )

                # ✅ Validate item
                db_item = await db.get(Item, item.item_id)
                if not db_item:
                    raise HTTPException(
                        404,
                        f"Item {item.item_id} not found"
                    )

                pricing = await resolve_pricing(
                    db, db_item, order.client_id, order.branch_id
                )
                snap = order_item_line_snapshot(pricing, item.quantity)
                total += snap["total_price"]

                db.add(build_order_item(
                    order.id, db_item.id, item.quantity, pricing
                ))

            order.total_amount = round(total, 2)

        # =========================
        # ✅ Commit
        # =========================
        await db.commit()
        await db.refresh(order)

        # =========================
        # ✅ Fetch Items for Response
        # =========================
        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        order_items = items_result.scalars().all()

        return {
            "id": order.id,
            "client_id": order.client_id,
            "branch_id": order.branch_id,
            "table_id": order.table_id,
            "order_type": order.order_type,
            "customer_name": order.customer_name,
            "customer_phone": order.customer_phone,
            "notes": order.notes,
            "status": order.status,
            "total_amount": order.total_amount,
            "created_at": order.created_at,
            "items": [
                {
                    "item_id": i.item_id,
                    "quantity": i.quantity,
                    "price": i.price
                } for i in order_items
            ]
        }

    # =========================
    # ✅ Exception Handling
    # =========================
    except HTTPException as e:
        await db.rollback()
        raise e

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            500,
            "Database error while updating order"
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            500,
            "Unexpected error occurred"
        )

# =========================
# ✅ CREATE ORDER (Already Good)
# =========================
@router.post("/create_order")
async def create_order(
    data: OrderCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    try:
        role = current["role"]
        user = current["user"]

        # Enforce staff's client and branch to prevent client-side parameter errors
        if role == UserRole.STAFF:
            data.client_id = user.client_id
            data.branch_id = user.branch_id

        await get_client_if_accessible(data.client_id, db, current)

        order = Order(
            client_id=data.client_id,
            branch_id=data.branch_id,
            table_id=data.table_id,
            order_type=data.order_type,
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            notes=data.notes
        )

        db.add(order)
        await db.flush()

        if not data.items:
            raise HTTPException(400, "Order must contain at least one item")

        total = 0

        for item in data.items:
            if item.quantity <= 0:
                raise HTTPException(400, "Invalid quantity")

            db_item = await db.get(Item, item.item_id)
            if not db_item:
                raise HTTPException(404, f"Item {item.item_id} not found")

            pricing = await resolve_pricing(
                db, db_item, data.client_id, data.branch_id
            )
            snap = order_item_line_snapshot(pricing, item.quantity)
            total += snap["total_price"]

            db.add(build_order_item(
                order.id, db_item.id, item.quantity, pricing
            ))

        order.total_amount = round(total, 2)

        await db.commit()
        await db.refresh(order)

        return {
            "message": "Order created",
            "order_id": order.id,
            "total": total
        }

    except HTTPException as e:
        await db.rollback()
        raise e
    except SQLAlchemyError as e:
        await db.rollback()
        print("CREATE ORDER DB ERROR:", str(e))
        raise HTTPException(500, f"Database error: {str(e)}")
    except Exception as e:
        await db.rollback()
        print("CREATE ORDER UNEXPECTED ERROR:", str(e))
        raise HTTPException(500, f"Something went wrong: {str(e)}")