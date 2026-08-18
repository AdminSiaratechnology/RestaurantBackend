

from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.branch.model import Branch
from app.accounts.order.model import Order, OrderItem
from app.accounts.item.model import Item
from sqlalchemy.orm import selectinload
from app.accounts.pricing.model import Pricing
from app.accounts.table.model import Table







async def get_orders_all_branches(
    db,
    client_id: int,
):

    # =====================================================
    # 1. GET BRANCHES
    # =====================================================

    branches_result = await db.execute(
        select(Branch)
        .where(
            Branch.client_id == client_id
        )
    )

    branches = (
        branches_result
        .scalars()
        .all()
    )

    branch_ids = [
        branch.id
        for branch in branches
    ]

    if not branch_ids:

        return {
            "total_orders": 0,
            "branches": [],
        }

    # =====================================================
    # 2. GET ORDERS
    # =====================================================

    orders_result = await db.execute(
        select(Order)
        .where(
            Order.branch_id.in_(branch_ids)
        )
        .order_by(
            Order.id.desc()
        )
    )

    orders = (
        orders_result
        .scalars()
        .all()
    )

    order_ids = [
        order.id
        for order in orders
    ]

    if not order_ids:

        return {
            "total_orders": 0,

            "branches": [
                {
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "total_orders": 0,
                    "orders": [],
                }
                for branch in branches
            ],
        }

    # =====================================================
    # 3. GET ORDER ITEMS
    # =====================================================

    items_result = await db.execute(
        select(OrderItem)
        .where(
            OrderItem.order_id.in_(
                order_ids
            )
        )
    )

    order_items = (
        items_result
        .scalars()
        .all()
    )

    # =====================================================
    # 4. ORDER -> ITEMS MAP
    # =====================================================

    items_map = {}

    for order_item in order_items:

        items_map.setdefault(
            order_item.order_id,
            [],
        ).append(
            order_item
        )

    # =====================================================
    # 5. GET ITEM NAMES
    # =====================================================

    item_ids = list(
        {
            order_item.item_id
            for order_item in order_items
        }
    )

    item_map = {}

    if item_ids:

        item_result = await db.execute(
            select(Item)
            .where(
                Item.id.in_(item_ids)
            )
        )

        item_map = {
            item.id: item.name
            for item in (
                item_result
                .scalars()
                .all()
            )
        }

    # =====================================================
    # 6. GET TABLES
    #
    # tables.id
    # tables.name
    #
    # Order:
    # order.table_id
    #
    # API:
    # table_id
    # table_name
    # =====================================================

    table_ids = list(
        {
            order.table_id
            for order in orders
            if order.table_id is not None
        }
    )

    table_map = {}

    if table_ids:

        table_result = await db.execute(
            select(Table)
            .where(
                Table.id.in_(table_ids)
            )
        )

        tables = (
            table_result
            .scalars()
            .all()
        )

        table_map = {
            table.id: table
            for table in tables
        }

    # =====================================================
    # 7. RESPONSE
    # =====================================================

    response = {
        "total_orders": len(orders),
        "branches": [],
    }

    for branch in branches:

        branch_orders = [
            order
            for order in orders
            if order.branch_id == branch.id
        ]

        final_orders = []

        for order in branch_orders:

            # =================================================
            # TABLE
            # =================================================

            table_name = None

            if order.table_id is not None:

                table = table_map.get(
                    order.table_id
                )

                if table:

                    table_name = table.name

                    if table.floor:

                        table_name = (
                            f"{table.name} "
                            f"({table.floor})"
                        )

            # =================================================
            # ITEMS
            # =================================================

            final_items = []

            for order_item in (
                items_map.get(
                    order.id,
                    [],
                )
            ):

                item_name = (
                    item_map.get(
                        order_item.item_id
                    )
                )

                final_items.append(
                    {
                        "id": (
                            order_item.id
                        ),

                        "item_id": (
                            order_item.item_id
                        ),

                        "item_name": (
                            item_name
                        ),

                        "name": (
                            item_name
                        ),

                        "quantity": (
                            order_item.quantity
                        ),

                        "unit_price": (
                            order_item.unit_price
                        ),

                        "price": (
                            order_item.unit_price
                        ),

                        "order_status": (
                            order_item.order_status
                        ),
                    }
                )

            # =================================================
            # ORDER
            # =================================================

            final_orders.append(
                {
                    "order_id": order.id,

                    "id": order.id,

                    "branch_id": (
                        branch.id
                    ),

                    "branch_name": (
                        branch.name
                    ),

                    "table_id": (
                        order.table_id
                    ),

                    # IMPORTANT
                    "table_name": (
                        table_name
                    ),

                    "order_type": (
                        order.order_type
                    ),

                    "customer_name": (
                        order.customer_name
                    ),

                    "customer_phone": (
                        order.customer_phone
                    ),

                    "notes": (
                        order.notes
                    ),

                    "status": (
                        order.status
                    ),

                    "total_amount": (
                        order.total_amount
                    ),

                    "created_at": (
                        order.created_at
                    ),

                    "items": (
                        final_items
                    ),
                }
            )

        response["branches"].append(
            {
                "branch_id": branch.id,

                "branch_name": (
                    branch.name
                ),

                "total_orders": (
                    len(branch_orders)
                ),

                "orders": (
                    final_orders
                ),
            }
        )

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



