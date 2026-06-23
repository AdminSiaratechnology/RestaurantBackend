from sqlalchemy import select, func

from app.accounts.order.model import OrderItem, Order
from app.accounts.category.model import Category
from app.accounts.item.model import Item
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.rep_menu.schema import (
    CategoryDistributionItem,
    CategoryDistributionResponse,
    MenuDashboardResponse,
    TopSellingItem,
    TopSellingItemsResponse
)


async def get_category_distribution_service(
    db,
    branch_id: int
):
    result = await db.execute(
        select(
            Category.id,
            Category.name,
            func.count(Item.id).label("item_count")
        )
        .outerjoin(
            Item,
            Item.category_id == Category.id
        )
        .where(
            Category.branch_id == branch_id
        )
        .group_by(
            Category.id,
            Category.name
        )
        .order_by(
            func.count(Item.id).desc()
        )
    )

    rows = result.all()

    total_items = sum(
        row.item_count for row in rows
    )

    categories = []

    for row in rows:
        percentage = (
            round(
                (row.item_count / total_items) * 100,
                2
            )
            if total_items > 0
            else 0
        )

        categories.append(
            CategoryDistributionItem(
                category_id=row.id,
                category_name=row.name,
                item_count=row.item_count,
                percentage=percentage
            )
        )

    return CategoryDistributionResponse(
        total_items=total_items,
        categories=categories
    )


async def dashboard_summary_service(
    db,
    branch_id: int
):
    total_categories = await db.scalar(
        select(
            func.count(Category.id)
        ).where(
            Category.branch_id == branch_id
        )
    )

    total_items = await db.scalar(
        select(
            func.count(Item.id)
        ).where(
            Item.branch_id == branch_id
        )
    )

    active_items = await db.scalar(
        select(
            func.count(Item.id)
        ).where(
            Item.branch_id == branch_id,
            Item.is_active.is_(True)
        )
    )

    return MenuDashboardResponse(
        total_categories=total_categories or 0,
        total_items=total_items or 0,
        active_items=active_items or 0
    )


async def get_top_selling_items_service(
    db,
    branch_id: int
):
    result = await db.execute(
        select(
            Item.id.label("item_id"),
            Item.name.label("item_name"),
            func.sum(
                OrderItem.quantity
            ).label("quantity_sold")
        )
        .join(
            OrderItem,
            OrderItem.item_id == Item.id
        )
        .join(
            Order,
            Order.id == OrderItem.order_id
        )
        .join(
            Bill,
            Bill.order_id == Order.id
        )
        .where(
            Order.branch_id == branch_id,
            Bill.payment_status == PaymentStatus.complete
        )
        .group_by(
            Item.id,
            Item.name
        )
        .order_by(
            func.sum(
                OrderItem.quantity
            ).desc()
        )
        .limit(10)
    )

    rows = result.all()

    total_quantity = sum(
        row.quantity_sold for row in rows
    )

    items = []

    for row in rows:
        percentage = (
            round(
                (row.quantity_sold / total_quantity) * 100,
                2
            )
            if total_quantity > 0
            else 0
        )

        items.append(
            TopSellingItem(
                item_id=row.item_id,
                item_name=row.item_name,
                quantity_sold=row.quantity_sold,
                percentage=percentage
            )
        )

    return TopSellingItemsResponse(
        total_quantity_sold=total_quantity,
        items=items
    )



from fastapi import HTTPException
from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.category.model import Category
from app.accounts.item.model import Item
from app.accounts.enum import UserRole


async def menu_dashboard_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    if not branches:
        return {
            "total_categories": 0,
            "total_items": 0,
            "active_items": 0,
            "branches": []
        }

    response = {
        "total_categories": 0,
        "total_items": 0,
        "active_items": 0,
        "branches": []
    }

    for branch in branches:

        total_categories = await db.scalar(
            select(
                func.count(Category.id)
            ).where(
                Category.branch_id == branch.id
            )
        )

        total_items = await db.scalar(
            select(
                func.count(Item.id)
            ).where(
                Item.branch_id == branch.id
            )
        )

        active_items = await db.scalar(
            select(
                func.count(Item.id)
            ).where(
                Item.branch_id == branch.id,
                Item.is_active.is_(True)
            )
        )

        response["total_categories"] += (
            total_categories or 0
        )

        response["total_items"] += (
            total_items or 0
        )

        response["active_items"] += (
            active_items or 0
        )

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,

            "total_categories": total_categories or 0,
            "total_items": total_items or 0,
            "active_items": active_items or 0
        })

    return response


from fastapi import HTTPException
from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.item.model import Item
from app.accounts.order.model import Order, OrderItem
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.enum import UserRole


async def get_top_selling_items_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch.id).where(
            Branch.client_id == user.id
        )
    )

    branch_ids = branches_result.scalars().all()

    if not branch_ids:
        return {
            "total_quantity_sold": 0,
            "items": []
        }

    result = await db.execute(
        select(
            Item.id.label("item_id"),
            Item.name.label("item_name"),
            func.sum(
                OrderItem.quantity
            ).label("quantity_sold")
        )
        .join(
            OrderItem,
            OrderItem.item_id == Item.id
        )
        .join(
            Order,
            Order.id == OrderItem.order_id
        )
        .join(
            Bill,
            Bill.order_id == Order.id
        )
        .where(
            Order.branch_id.in_(branch_ids),
            Bill.payment_status == PaymentStatus.complete
        )
        .group_by(
            Item.id,
            Item.name
        )
        .order_by(
            func.sum(
                OrderItem.quantity
            ).desc()
        )
        .limit(10)
    )

    rows = result.all()

    total_quantity = sum(
        row.quantity_sold
        for row in rows
    )

    items = []

    for row in rows:

        percentage = (
            round(
                (
                    row.quantity_sold
                    / total_quantity
                ) * 100,
                2
            )
            if total_quantity > 0
            else 0
        )

        items.append({
            "item_id": row.item_id,
            "item_name": row.item_name,
            "quantity_sold": row.quantity_sold,
            "percentage": percentage
        })

    return {
        "total_quantity_sold": total_quantity,
        "items": items
    }


from fastapi import HTTPException
from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.category.model import Category
from app.accounts.item.model import Item
from app.accounts.enum import UserRole


async def get_category_distribution_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    response = {
        "total_items": 0,
        "branches": []
    }

    for branch in branches:

        result = await db.execute(
            select(
                Category.id,
                Category.name,
                func.count(Item.id).label("item_count")
            )
            .outerjoin(
                Item,
                Item.category_id == Category.id
            )
            .where(
                Category.branch_id == branch.id
            )
            .group_by(
                Category.id,
                Category.name
            )
            .order_by(
                func.count(Item.id).desc()
            )
        )

        rows = result.all()

        branch_total_items = sum(
            row.item_count for row in rows
        )

        response["total_items"] += branch_total_items

        categories = []

        for row in rows:

            percentage = (
                round(
                    (row.item_count / branch_total_items) * 100,
                    2
                )
                if branch_total_items > 0
                else 0
            )

            categories.append({
                "category_id": row.id,
                "category_name": row.name,
                "item_count": row.item_count,
                "percentage": percentage
            })

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_items": branch_total_items,
            "categories": categories
        })

    return response