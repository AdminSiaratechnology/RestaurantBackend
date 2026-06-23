# =========================================================
# app/accounts/rep_inventory/routers.py
# =========================================================

from fastapi import APIRouter, Query, Depends
from app.accounts.deps import access_four
from app.db.config import SessionDep

from app.accounts.rep_inventory.schema import (
    InventoryDashboardResponse
)

from app.accounts.rep_inventory.service import (
    get_inventory_dashboard_all_branches_service,
    get_inventory_dashboard_service
)

router = APIRouter(
    prefix="/reports/inventory",
    tags=["Inventory Reports"]
)


@router.get(
    "/dashboard-summary",
    response_model=InventoryDashboardResponse
)
async def get_inventory_dashboard(
    db: SessionDep,
    branch_id: int = Query(...)
):
    return await get_inventory_dashboard_service(
        db=db,
        branch_id=branch_id
    )



@router.get(
    "/dashboard-summary/all-branches"
)
async def get_inventory_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_inventory_dashboard_all_branches_service(
        db=db,
        current=current
    )