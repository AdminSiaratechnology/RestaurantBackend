

from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.branch.model import Branch
from app.accounts.order.model import Order, OrderItem
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing


async def get_orders_all_branches(db, client_id: int):
    # 1. get all branches
    branches_result = await db.execute(
        select(Branch).where(Branch.client_id == client_id)
    )
    branches = branches_result.scalars().all()

    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "total_orders": 0,
            "branches": []
        }

    # 2. get all orders of client branches
    orders_result = await db.execute(
        select(Order).where(Order.branch_id.in_(branch_ids))
    )
    orders = orders_result.scalars().all()

    # 3. get order items separately
    items_result = await db.execute(
        select(OrderItem)
        .where(OrderItem.order_id.in_([o.id for o in orders]))
    )
    items = items_result.scalars().all()

    # map items by order_id
    items_map = {}
    for i in items:
        items_map.setdefault(i.order_id, []).append(i)

    response = {
        "total_orders": len(orders),
        "branches": []
    }

    for branch in branches:

        branch_orders = [o for o in orders if o.branch_id == branch.id]

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_orders": len(branch_orders),

            "orders": [
                {
                    "order_id": o.id,
                    "table_id": o.table_id,
                    "order_type": o.order_type,
                    "status": o.status,
                    "total_amount": o.total_amount,
                    "created_at": o.created_at,

                    "items": [
                        {
                            "id": i.id,
                            "item_id": i.item_id,
                            "quantity": i.quantity,
                            "unit_price": i.unit_price,
                            "order_status": i.order_status,
                        }
                        for i in items_map.get(o.id, [])
                    ]
                }
                for o in branch_orders
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



