# app/reports/category/queries.py

from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.category.model import Category
from app.accounts.item.model import Item
from app.accounts.order.model import Order, OrderItem
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus


async def query_categories_with_item_counts(
    db: AsyncSession,
    branch_ids: List[int],
    search_query: Optional[str] = None,
):
    """
    Fetches categories for the given branches with count of total items and active items.
    Uses outerjoin so categories with 0 items are preserved.
    """
    conditions = [Category.branch_id.in_(branch_ids)]
    if search_query:
        conditions.append(Category.name.ilike(f"%{search_query.strip()}%"))

    stmt = (
        select(
            Category.id,
            Category.branch_id,
            Category.name,
            Category.icon,
            func.count(Item.id).label("item_count"),
            func.coalesce(
                func.sum(
                    case((Item.is_active.is_(True), 1), else_=0)
                ),
                0,
            ).label("active_items"),
        )
        .outerjoin(Item, Item.category_id == Category.id)
        .where(*conditions)
        .group_by(Category.id, Category.branch_id, Category.name, Category.icon)
        .order_by(Category.name.asc())
    )

    res = await db.execute(stmt)
    return res.all()


async def query_category_sales_aggregations(
    db: AsyncSession,
    branch_ids: List[int],
    start_dt: datetime,
    end_dt: datetime,
):
    """
    Calculates sold quantity and sales amount grouped by category for completed orders.
    """
    stmt = (
        select(
            Item.category_id,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("sold_qty"),
            func.coalesce(func.sum(OrderItem.total_price), 0).label("sold_amount"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(Item, Item.id == OrderItem.item_id)
        .join(Bill, Bill.order_id == Order.id)
        .where(
            Order.branch_id.in_(branch_ids),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Bill.payment_status == PaymentStatus.complete,
            Item.category_id.isnot(None),
        )
        .group_by(Item.category_id)
    )

    res = await db.execute(stmt)
    return res.all()


async def query_category_items_detail(
    db: AsyncSession,
    branch_ids: List[int],
    start_dt: datetime,
    end_dt: datetime,
):
    """
    Fetches detailed line-item breakdown per category and dish for Sheet 2 of Excel export.
    """
    stmt = (
        select(
            Category.name.label("category_name"),
            Item.id.label("item_id"),
            Item.name.label("item_name"),
            Item.food_type,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty_sold"),
            func.coalesce(func.sum(OrderItem.total_price), 0).label("revenue"),
            func.avg(OrderItem.unit_price).label("avg_unit_price"),
        )
        .join(Item, Item.category_id == Category.id)
        .outerjoin(OrderItem, OrderItem.item_id == Item.id)
        .outerjoin(Order, (Order.id == OrderItem.order_id) & (Order.created_at >= start_dt) & (Order.created_at <= end_dt))
        .where(Category.branch_id.in_(branch_ids))
        .group_by(Category.name, Item.id, Item.name, Item.food_type)
        .order_by(Category.name.asc(), func.sum(OrderItem.total_price).desc())
    )

    res = await db.execute(stmt)
    return res.all()
