from fastapi import APIRouter, Depends

from app.db.config import SessionDep

from app.accounts.rep_sales.schema import (
    DashboardSummaryResponse
)

from app.accounts.rep_sales.service import (
    get_dashboard_summary_service,
    sales_dashboard_all_branches_service
)

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
    return await get_dashboard_summary_service(
        db=db,
        branch_id=branch_id
    )



from app.accounts.deps import access_four

@router.get(
    "/dashboard-summary/all-branches"
)
async def sales_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await sales_dashboard_all_branches_service(
        db=db,
        current=current
    )