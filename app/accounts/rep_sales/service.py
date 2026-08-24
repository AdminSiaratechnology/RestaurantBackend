from datetime import datetime, timedelta, date

from fastapi import HTTPException
from sqlalchemy import select, func

from app.accounts.order.model import Order
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.branch.model import Branch
from app.accounts.enum import UserRole

from app.accounts.rep_sales.schema import (
    DashboardSummaryResponse,
    SalesTrendItem,
    SalesTrendResponse,
    SalesDashboardResponse,
    BranchSalesSummary,
    AllBranchesSalesResponse,
)

from app.core.cache import Cache


# =========================================================
# DATE HELPERS
# =========================================================

def get_week_range():
    """
    Monday 00:00:00 -> Sunday 23:59:59
    """

    today = datetime.utcnow()

    start_of_week = (
        today - timedelta(days=today.weekday())
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_of_week = (
        start_of_week + timedelta(days=7)
    )

    return start_of_week, end_of_week


# =========================================================
# DASHBOARD SUMMARY
# =========================================================

async def get_dashboard_summary_service(
    db,
    branch_id: int,
):
    today_str = date.today().isoformat()

    cache_key = (
        f"report:{branch_id}:sales_summary:{today_str}"
    )

    cached = await Cache.get(cache_key)

    if cached:
        return DashboardSummaryResponse(**cached)

    start_of_week, end_of_week = get_week_range()

    # =====================================================
    # THIS WEEK ORDERS
    # =====================================================

    orders_result = await db.execute(
        select(
            func.count(Order.id)
        ).where(
            Order.branch_id == branch_id,

            Order.created_at >= start_of_week,

            Order.created_at < end_of_week,
        )
    )

    this_week_orders = (
        orders_result.scalar() or 0
    )

    # =====================================================
    # THIS WEEK REVENUE
    # =====================================================

    revenue_result = await db.execute(
        select(
            func.coalesce(
                func.sum(Bill.final_amount),
                0,
            )
        ).where(
            Bill.branch_id == branch_id,

            Bill.created_at >= start_of_week,

            Bill.created_at < end_of_week,

            Bill.payment_status == PaymentStatus.complete,
        )
    )

    this_week_revenue = (
        revenue_result.scalar() or 0
    )

    # =====================================================
    # AVG DAILY ORDERS
    # =====================================================

    avg_daily_orders = round(
        this_week_orders / 7,
        1,
    )

    result = DashboardSummaryResponse(
        this_week_orders=int(
            this_week_orders
        ),

        this_week_revenue=round(
            float(this_week_revenue),
            2,
        ),

        avg_daily_orders=avg_daily_orders,
    )

    await Cache.set(
        cache_key,
        result.model_dump(),
        expire=21600,
    )

    return result


# =========================================================
# SALES TREND
# =========================================================

async def get_sales_trend_service(
    db,
    branch_id: int,
    period: str,
):
    period = period.lower()

    today = datetime.utcnow()

    # =====================================================
    # TODAY
    # =====================================================

    if period == "today":

        start_date = today.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        end_date = start_date + timedelta(days=1)

        result = await db.execute(
            select(
                func.extract(
                    "hour",
                    Bill.created_at,
                ).label("hour"),

                func.count(Bill.id).label(
                    "orders"
                ),

                func.coalesce(
                    func.sum(
                        Bill.final_amount
                    ),
                    0,
                ).label("revenue"),
            )
            .where(
                Bill.branch_id == branch_id,

                Bill.created_at >= start_date,

                Bill.created_at < end_date,

                Bill.payment_status
                == PaymentStatus.complete,
            )
            .group_by(
                func.extract(
                    "hour",
                    Bill.created_at,
                )
            )
            .order_by(
                func.extract(
                    "hour",
                    Bill.created_at,
                )
            )
        )

        rows = result.all()

        data = []

        row_map = {
            int(row.hour): row
            for row in rows
        }

        for hour in range(24):

            row = row_map.get(hour)

            data.append(
                SalesTrendItem(
                    label=f"{hour:02d}:00",

                    date=start_date.date().isoformat(),

                    orders=(
                        int(row.orders)
                        if row
                        else 0
                    ),

                    revenue=round(
                        float(
                            row.revenue
                        )
                        if row
                        else 0,
                        2,
                    ),
                )
            )

    # =====================================================
    # LAST 7 DAYS
    # =====================================================

    elif period in (
        "7d",
        "7days",
        "week",
    ):

        start_date = (
            today.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            - timedelta(days=6)
        )

        end_date = (
            today.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            + timedelta(days=1)
        )

        result = await db.execute(
            select(
                func.date(
                    Bill.created_at
                ).label("sale_date"),

                func.count(
                    Bill.id
                ).label("orders"),

                func.coalesce(
                    func.sum(
                        Bill.final_amount
                    ),
                    0,
                ).label("revenue"),
            )
            .where(
                Bill.branch_id == branch_id,

                Bill.created_at >= start_date,

                Bill.created_at < end_date,

                Bill.payment_status
                == PaymentStatus.complete,
            )
            .group_by(
                func.date(
                    Bill.created_at
                )
            )
            .order_by(
                func.date(
                    Bill.created_at
                )
            )
        )

        rows = result.all()

        row_map = {
            row.sale_date: row
            for row in rows
        }

        data = []

        for i in range(7):

            current_date = (
                start_date.date()
                + timedelta(days=i)
            )

            row = row_map.get(
                current_date
            )

            data.append(
                SalesTrendItem(
                    label=current_date.strftime(
                        "%a"
                    ),

                    date=current_date.isoformat(),

                    orders=(
                        int(row.orders)
                        if row
                        else 0
                    ),

                    revenue=round(
                        float(
                            row.revenue
                        )
                        if row
                        else 0,
                        2,
                    ),
                )
            )

    # =====================================================
    # THIS MONTH
    # =====================================================

    elif period in (
        "month",
        "30d",
    ):

        start_date = today.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        if start_date.month == 12:

            end_date = start_date.replace(
                year=start_date.year + 1,
                month=1,
                day=1,
            )

        else:

            end_date = start_date.replace(
                month=start_date.month + 1,
                day=1,
            )

        result = await db.execute(
            select(
                func.date(
                    Bill.created_at
                ).label("sale_date"),

                func.count(
                    Bill.id
                ).label("orders"),

                func.coalesce(
                    func.sum(
                        Bill.final_amount
                    ),
                    0,
                ).label("revenue"),
            )
            .where(
                Bill.branch_id == branch_id,

                Bill.created_at >= start_date,

                Bill.created_at < end_date,

                Bill.payment_status
                == PaymentStatus.complete,
            )
            .group_by(
                func.date(
                    Bill.created_at
                )
            )
            .order_by(
                func.date(
                    Bill.created_at
                )
            )
        )

        rows = result.all()

        row_map = {
            row.sale_date: row
            for row in rows
        }

        data = []

        current_date = start_date.date()

        while current_date < end_date.date():

            row = row_map.get(
                current_date
            )

            data.append(
                SalesTrendItem(
                    label=current_date.strftime(
                        "%d"
                    ),

                    date=current_date.isoformat(),

                    orders=(
                        int(row.orders)
                        if row
                        else 0
                    ),

                    revenue=round(
                        float(
                            row.revenue
                        )
                        if row
                        else 0,
                        2,
                    ),
                )
            )

            current_date += timedelta(
                days=1
            )

    else:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid period. "
                "Use today, 7d or month."
            ),
        )

    total_orders = sum(
        item.orders
        for item in data
    )

    total_revenue = sum(
        item.revenue
        for item in data
    )

    return SalesTrendResponse(
        period=period,

        total_orders=total_orders,

        total_revenue=round(
            total_revenue,
            2,
        ),

        data=data,
    )


# =========================================================
# COMPLETE BRANCH SALES DASHBOARD
# =========================================================

async def get_sales_dashboard_service(
    db,
    branch_id: int,
    period: str = "7d",
):
    summary = await get_dashboard_summary_service(
        db=db,
        branch_id=branch_id,
    )

    trend = await get_sales_trend_service(
        db=db,
        branch_id=branch_id,
        period=period,
    )

    return SalesDashboardResponse(
        summary=summary,
        trend=trend,
    )


# =========================================================
# ALL BRANCHES
# =========================================================

async def sales_dashboard_all_branches_service(
    db,
    current,
):
    role = current["role"]

    user = current["user"]

    if role != UserRole.CLIENT:

        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    start_of_week, end_of_week = (
        get_week_range()
    )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = (
        branches_result.scalars().all()
    )

    if not branches:

        return AllBranchesSalesResponse(
            this_week_orders=0,

            this_week_revenue=0,

            avg_daily_orders=0,

            branches=[],
        )

    total_orders = 0

    total_revenue = 0

    branch_data = []

    for branch in branches:

        # =================================================
        # ORDERS
        # =================================================

        orders_result = await db.execute(
            select(
                func.count(Order.id)
            ).where(
                Order.branch_id == branch.id,

                Order.created_at >= start_of_week,

                Order.created_at < end_of_week,
            )
        )

        orders = (
            orders_result.scalar() or 0
        )

        # =================================================
        # REVENUE
        # =================================================

        revenue_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        Bill.final_amount
                    ),
                    0,
                )
            ).where(
                Bill.branch_id == branch.id,

                Bill.created_at >= start_of_week,

                Bill.created_at < end_of_week,

                Bill.payment_status
                == PaymentStatus.complete,
            )
        )

        revenue = float(
            revenue_result.scalar() or 0
        )

        avg_daily_orders = round(
            orders / 7,
            1,
        )

        total_orders += orders

        total_revenue += revenue

        branch_data.append(
            BranchSalesSummary(
                branch_id=branch.id,

                branch_name=branch.name,

                this_week_orders=int(
                    orders
                ),

                this_week_revenue=round(
                    revenue,
                    2,
                ),

                avg_daily_orders=avg_daily_orders,
            )
        )

    return AllBranchesSalesResponse(
        this_week_orders=int(
            total_orders
        ),

        this_week_revenue=round(
            total_revenue,
            2,
        ),

        avg_daily_orders=round(
            total_orders / 7,
            1,
        ),

        branches=branch_data,
    )