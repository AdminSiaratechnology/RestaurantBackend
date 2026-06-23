from fastapi import APIRouter, Query, Depends

from app.db.config import SessionDep
from app.accounts.deps import access_four
from app.accounts.rep_financial.schema import (
    DashboardSummaryResponse,
    TaxCollectedResponse
)

from app.accounts.rep_financial.service import (
    dashboard_summary_service,
    financial_dashboard_all_branches_service,
    get_tax_collected_service,
    tax_collected_all_branches_service
)

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
    return await dashboard_summary_service(
        db=db,
        branch_id=branch_id
    )


@router.get(
    "/tax-collected",
    response_model=TaxCollectedResponse
)
async def get_tax_collected(
    db: SessionDep,
    branch_id: int = Query(...)
):
    return await get_tax_collected_service(
        db=db,
        branch_id=branch_id
    )




@router.get(
    "/dashboard-summary/all-branches"
)
async def financial_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await financial_dashboard_all_branches_service(
        db=db,
        current=current
    )



@router.get(
    "/tax-collected/all-branches"
)
async def tax_collected_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await tax_collected_all_branches_service(
        db=db,
        current=current
    )