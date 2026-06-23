from datetime import datetime, timedelta

from sqlalchemy import select, func

from app.accounts.order.model import Order
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.rep_sales.schema import (
    DashboardSummaryResponse
)


async def get_dashboard_summary_service(
    db,
    branch_id: int
):
    today = datetime.utcnow()

    start_of_week = (
        today - timedelta(days=today.weekday())
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    end_of_week = (
        start_of_week + timedelta(days=5)
    ).replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=999999
    )

    # ==========================================
    # THIS WEEK ORDERS
    # ==========================================

    orders_result = await db.execute(
        select(
            func.count(Order.id)
        ).where(
            Order.branch_id == branch_id,
            Order.created_at >= start_of_week,
            Order.created_at <= end_of_week
        )
    )

    this_week_orders = (
        orders_result.scalar() or 0
    )

    # ==========================================
    # THIS WEEK REVENUE
    # ==========================================

    revenue_result = await db.execute(
        select(
            func.coalesce(
                func.sum(Bill.grand_total),
                0
            )
        ).where(
            Bill.branch_id == branch_id,
            Bill.created_at >= start_of_week,
            Bill.created_at <= end_of_week,
            Bill.payment_status == PaymentStatus.complete
        )
    )

    this_week_revenue = (
        revenue_result.scalar() or 0
    )

    avg_daily_orders = round(
        this_week_orders / 6,
        1
    )

    return DashboardSummaryResponse(
        this_week_orders=this_week_orders,
        this_week_revenue=round(
            float(this_week_revenue),
            2
        ),
        avg_daily_orders=avg_daily_orders
    )



from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.order.model import Order
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.enum import UserRole


async def sales_dashboard_all_branches_service(
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

    today = datetime.utcnow()

    start_of_week = (
        today - timedelta(days=today.weekday())
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    end_of_week = (
        start_of_week + timedelta(days=5)
    ).replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=999999
    )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    if not branches:
        return {
            "this_week_orders": 0,
            "this_week_revenue": 0,
            "avg_daily_orders": 0,
            "branches": []
        }

    response = {
        "this_week_orders": 0,
        "this_week_revenue": 0,
        "avg_daily_orders": 0,
        "branches": []
    }

    for branch in branches:

        orders_result = await db.execute(
            select(
                func.count(Order.id)
            ).where(
                Order.branch_id == branch.id,
                Order.created_at >= start_of_week,
                Order.created_at <= end_of_week
            )
        )

        revenue_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(Bill.grand_total),
                    0
                )
            ).where(
                Bill.branch_id == branch.id,
                Bill.created_at >= start_of_week,
                Bill.created_at <= end_of_week,
                Bill.payment_status == PaymentStatus.complete
            )
        )

        orders = orders_result.scalar() or 0
        revenue = float(
            revenue_result.scalar() or 0
        )

        avg_daily_orders = round(
            orders / 6,
            1
        )

        response["this_week_orders"] += orders
        response["this_week_revenue"] += revenue

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,

            "this_week_orders": orders,
            "this_week_revenue": round(
                revenue,
                2
            ),
            "avg_daily_orders": avg_daily_orders
        })

    response["this_week_revenue"] = round(
        response["this_week_revenue"],
        2
    )

    response["avg_daily_orders"] = round(
        response["this_week_orders"] / 6,
        1
    )

    return response