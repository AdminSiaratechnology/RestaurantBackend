

from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.branch.model import Branch
from app.accounts.order.model import Order, OrderItem
from app.accounts.item.model import Item
from sqlalchemy.orm import selectinload
from app.accounts.pricing.model import Pricing







async def get_orders_all_branches(db, client_id: int):

    # =====================================
    # Get all branches
    # =====================================
    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == client_id
        )
    )
    branches = branches_result.scalars().all()

    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "total_orders": 0,
            "branches": []
        }

    # =====================================
    # Get all orders
    # =====================================
    orders_result = await db.execute(
        select(Order).where(
            Order.branch_id.in_(branch_ids)
        )
    )
    orders = orders_result.scalars().all()

    order_ids = [o.id for o in orders]

    if not order_ids:
        return {
            "total_orders": 0,
            "branches": [
                {
                    "branch_id": b.id,
                    "branch_name": b.name,
                    "total_orders": 0,
                    "orders": []
                }
                for b in branches
            ]
        }

    # =====================================
    # Get all order items
    # =====================================
    items_result = await db.execute(
        select(OrderItem).where(
            OrderItem.order_id.in_(order_ids)
        )
    )
    order_items = items_result.scalars().all()

    # =====================================
    # Create order_id -> items mapping
    # =====================================
    items_map = {}

    for item in order_items:
        items_map.setdefault(item.order_id, []).append(item)

    # =====================================
    # Get item names
    # =====================================
    item_ids = list({item.item_id for item in order_items})

    item_map = {}

    if item_ids:
        item_result = await db.execute(
            select(Item).where(
                Item.id.in_(item_ids)
            )
        )

        item_map = {
            item.id: item.name
            for item in item_result.scalars().all()
        }

    # =====================================
    # Build Response
    # =====================================
    response = {
        "total_orders": len(orders),
        "branches": []
    }

    for branch in branches:

        branch_orders = [
            order for order in orders
            if order.branch_id == branch.id
        ]

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_orders": len(branch_orders),

            "orders": [
                {
                    "order_id": order.id,
                    "id": order.id,
                    "branch_id": branch.id,
                    "branch_name": branch.name,
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
                            "id": oi.id,
                            "item_id": oi.item_id,
                            "item_name": item_map.get(oi.item_id),
                            "name": item_map.get(oi.item_id),
                            "quantity": oi.quantity,
                            "unit_price": oi.unit_price,
                            "price": oi.unit_price,
                            "order_status": oi.order_status,
                        }
                        for oi in items_map.get(order.id, [])
                    ]
                }
                for order in branch_orders
            ]
        })

    return response

async def get_menu_all_branches(db, client_id: int):

    # 1. get branches
    branches_result = await db.execute(
        select(Branch).where(Branch.client_id == client_id)
    )
    branches = branches_result.scalars().all()

    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "total_items": 0,
            "branches": []
        }

    # 2. get items
    items_result = await db.execute(
        select(Item).where(Item.branch_id.in_(branch_ids))
    )
    items = items_result.scalars().all()

    # 3. get pricing
    pricing_result = await db.execute(
        select(Pricing).where(
            Pricing.branch_id.in_(branch_ids),
            Pricing.is_active == True
        )
    )
    pricings = pricing_result.scalars().all()

    pricing_map = {}
    for p in pricings:
        pricing_map[(p.item_id, p.branch_id)] = p

    response = {
        "total_items": len(items),
        "branches": []
    }

    for branch in branches:

        branch_items = [i for i in items if i.branch_id == branch.id]

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,

            "total_items": len(branch_items),

            "items": [
                {
                    "id": item.id,
                    "name": item.name,

                    "price": pricing_map.get(
                        (item.id, branch.id)
                    ).price if pricing_map.get((item.id, branch.id)) else 0,

                    "discount": pricing_map.get(
                        (item.id, branch.id)
                    ).discount if pricing_map.get((item.id, branch.id)) else 0,

                    "tax": pricing_map.get(
                        (item.id, branch.id)
                    ).tax if pricing_map.get((item.id, branch.id)) else 0,
                }
                for item in branch_items
            ]
        })

    return response



