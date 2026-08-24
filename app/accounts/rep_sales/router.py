from fastapi import APIRouter, Depends

from app.db.config import SessionDep

from app.accounts.deps import access_four

from app.accounts.rep_sales.schema import (
    DashboardSummaryResponse,
    SalesTrendResponse,
    SalesDashboardResponse,
    AllBranchesSalesResponse,
)

from app.accounts.rep_sales.service import (
    get_dashboard_summary_service,
    get_sales_trend_service,
    get_sales_dashboard_service,
    sales_dashboard_all_branches_service,
)


router = APIRouter(
    prefix="/reports/sales",
    tags=["Sales Reports"],
)


# =========================================================
# SINGLE BRANCH - KPI
# =========================================================

@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse,
)
async def get_dashboard_summary(
    branch_id: int,
    db: SessionDep,
):

    return await get_dashboard_summary_service(
        db=db,
        branch_id=branch_id,
    )


# =========================================================
# SINGLE BRANCH - SALES TREND
# =========================================================

@router.get(
    "/sales-trend",
    response_model=SalesTrendResponse,
)
async def get_sales_trend(
    branch_id: int,
    period: str = "7d",
    db: SessionDep = None,
):

    return await get_sales_trend_service(
        db=db,
        branch_id=branch_id,
        period=period,
    )


# =========================================================
# SINGLE BRANCH - COMPLETE DASHBOARD
# =========================================================

@router.get(
    "/dashboard",
    response_model=SalesDashboardResponse,
)
async def get_sales_dashboard(
    branch_id: int,
    period: str = "7d",
    db: SessionDep = None,
):

    return await get_sales_dashboard_service(
        db=db,
        branch_id=branch_id,
        period=period,
    )


# =========================================================
# ALL BRANCHES - CLIENT
# =========================================================

@router.get(
    "/dashboard-summary/all-branches",
    response_model=AllBranchesSalesResponse,
)
async def sales_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four),
):

    return await sales_dashboard_all_branches_service(
        db=db,
        current=current,
    )