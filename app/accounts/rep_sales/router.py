from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from app.db.config import SessionDep
from app.accounts.order.model import Order
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.rep_sales.schema import DashboardSummaryResponse

router = APIRouter(
    prefix="/reports/sales",
    tags=["Sales Reports"]
)


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse
)
async def get_dashboard_summary(
    branch_id: int,
    db: SessionDep
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

    this_week_orders = orders_result.scalar() or 0

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

    this_week_revenue = revenue_result.scalar() or 0

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