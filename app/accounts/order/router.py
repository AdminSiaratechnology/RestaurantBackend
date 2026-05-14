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


router = APIRouter(prefix="/order", tags=["Order"])

# =========================
# ✅ GET MENU
# =========================

@router.get("/menu")
async def get_menu(
    client_id: int,
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    try:
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

            price = pricing.price if pricing else 0

            menu.setdefault(category_name, []).append({
                "id": item.id,
                "name": item.name,
                "price": price
            })

        return menu

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error while fetching menu"
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

                # ✅ FIXED PRICING LOGIC (same as create)
                pricing_result = await db.execute(
                    select(Pricing).where(
                        Pricing.item_id == db_item.id,
                        Pricing.client_id == order.client_id,
                        Pricing.branch_id == order.branch_id,   # 🔥 include this
                        Pricing.is_active == True
                    )
                )

                pricing = pricing_result.scalar_one_or_none()

                # 🔁 fallback (optional but recommended)
                if not pricing:
                    pricing_result = await db.execute(
                        select(Pricing).where(
                            Pricing.item_id == db_item.id,
                            Pricing.client_id == order.client_id,
                            Pricing.is_active == True
                        )
                    )
                    pricing = pricing_result.scalar_one_or_none()

                if not pricing:
                    raise HTTPException(
                        400,
                        f"No active pricing found for item '{db_item.name}'"
                    )

                item_price = pricing.price
                total += item_price * item.quantity

                db.add(OrderItem(
                    order_id=order.id,
                    item_id=db_item.id,
                    quantity=item.quantity,
                    price=item_price
                ))

            order.total_amount = total

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

            pricing_result = await db.execute(
                select(Pricing).where(
                    Pricing.item_id == db_item.id,
                    Pricing.client_id == db_item.client_id,
                    Pricing.is_active == True
                )
            )
            pricing = pricing_result.scalar_one_or_none()

            if not pricing:
                raise HTTPException(400, f"No pricing for {db_item.name}")

            total += pricing.price * item.quantity

            db.add(OrderItem(
                order_id=order.id,
                item_id=db_item.id,
                quantity=item.quantity,
                price=pricing.price
            ))

        order.total_amount = total

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
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Database error")
    except Exception:
        await db.rollback()
        raise HTTPException(500, "Something went wrong")