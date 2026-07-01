# app/accounts/total_sales/service.py

from sqlalchemy import select, func
from datetime import datetime, date, timedelta

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.order.model import Order, OrderItem
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.branch.model import Branch
from app.core.cache import Cache


def get_today_range():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


class DashboardService:

    @staticmethod
    async def get_total_sales(
        db,
        client_id,
        branch_id=None
    ):
        today_str = date.today().isoformat()
        cache_key = f"report:{branch_id or f'all_client_{client_id}'}:total_sales:{today_str}"
        cached = await Cache.get(cache_key)
        if cached is not None:
            return cached
        conditions = [
            Bill.client_id == client_id,
            Bill.payment_status == PaymentStatus.complete
        ]

        if branch_id:
            conditions.append(
                Bill.branch_id == branch_id
            )

        result = await db.execute(
            select(
                func.coalesce(
                    func.sum(Bill.final_amount),
                    0
                )
            ).where(*conditions)
        )

        result_dict = {
            "total_sales": float(
                result.scalar() or 0
            )
        }
        await Cache.set(cache_key, result_dict, expire=21600)
        return result_dict

    @staticmethod
    async def get_orders_count(
        db,
        client_id,
        branch_id=None
    ):
        today_str = date.today().isoformat()
        cache_key = f"report:{branch_id or f'all_client_{client_id}'}:orders_count:{today_str}"
        cached = await Cache.get(cache_key)
        if cached is not None:
            return cached
        conditions = [
            Bill.client_id == client_id,
            Bill.payment_status == PaymentStatus.complete
        ]

        if branch_id:
            conditions.append(
                Bill.branch_id == branch_id
            )

        result = await db.execute(
            select(
                func.count(Bill.id)
            ).where(*conditions)
        )

        result_dict = {
            "orders": result.scalar() or 0
        }
        await Cache.set(cache_key, result_dict, expire=21600)
        return result_dict

    @staticmethod
    async def get_gross_profit(
        db,
        client_id,
        branch_id=None
    ):
        today_str = date.today().isoformat()
        cache_key = f"report:{branch_id or f'all_client_{client_id}'}:gross_profit:{today_str}"
        cached = await Cache.get(cache_key)
        if cached is not None:
            return cached
        conditions = [
            Bill.client_id == client_id,
            Bill.payment_status == PaymentStatus.complete
        ]

        if branch_id:
            conditions.append(
                Bill.branch_id == branch_id
            )

        sales_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(Bill.final_amount),
                    0
                )
            ).where(*conditions)
        )

        total_sales = float(
            sales_result.scalar() or 0
        )

        food_cost_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        OrderItem.quantity *
                        Pricing.cost_price
                    ),
                    0
                )
            )
            .join(
                Bill,
                Bill.order_id == OrderItem.order_id
            )
            .join(
                Item,
                Item.id == OrderItem.item_id
            )
            .join(
                Pricing,
                Pricing.item_id == Item.id
            )
            .where(*conditions)
        )

        food_cost = float(
            food_cost_result.scalar() or 0
        )

        result_dict = {
            "gross_profit": round(
                total_sales - food_cost,
                2
            )
        }
        await Cache.set(cache_key, result_dict, expire=21600)
        return result_dict