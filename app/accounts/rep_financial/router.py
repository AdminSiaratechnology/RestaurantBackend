from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.db.config import SessionDep
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.rep_financial.schema import DashboardSummaryResponse, TaxCollectedResponse

router = APIRouter(
    prefix="/reports/financial",
    tags=["Financial Reports"]
)


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse
)
async def dashboard_summary(
    db: SessionDep,
    branch_id: int
):
    revenue_result = await db.execute(
        select(
            func.coalesce(
                func.sum(Bill.grand_total),
                0
            )
        ).where(
            Bill.payment_status == PaymentStatus.complete,
            Bill.branch_id == branch_id
        )
    )

    orders_result = await db.execute(
        select(
            func.count(Bill.id)
        ).where(
            Bill.payment_status == PaymentStatus.complete,
            Bill.branch_id == branch_id
        )
    )

    total_revenue = revenue_result.scalar() or 0
    paid_orders = orders_result.scalar() or 0

    return DashboardSummaryResponse(
        total_revenue=round(float(total_revenue), 2),
        paid_orders=paid_orders
    )


@router.get(
    "/tax-collected",
    response_model=TaxCollectedResponse
)
async def get_tax_collected(
    db: SessionDep,
    branch_id: int = Query(...)
):
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    Bill.tax_total +
                    Bill.service_charge_amount
                ),
                0
            )
        ).where(
            Bill.payment_status == PaymentStatus.complete,
            Bill.branch_id == branch_id
        )
    )

    total_tax_collected = result.scalar() or 0

    return TaxCollectedResponse(
        total_tax_collected=round(
            float(total_tax_collected),
            2
        )
    )