# app/accounts/total_sales/routers.py

from fastapi import APIRouter, Depends

from app.db.config import SessionDep
from app.accounts.deps import access_one

from app.accounts.total_sales.service import (
    DashboardService
)

router = APIRouter(
    prefix="/total-sales",
    tags=["Total Sales"]
)


@router.get("/sales")
async def get_total_sales(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    return await DashboardService.get_total_sales(
        db=db,
        client_id=current["user"].id,
        branch_id=branch_id
    )


@router.get("/orders")
async def get_orders_count(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    return await DashboardService.get_orders_count(
        db=db,
        client_id=current["user"].id,
        branch_id=branch_id
    )


@router.get("/gross-profit")
async def get_gross_profit(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    return await DashboardService.get_gross_profit(
        db=db,
        client_id=current["user"].id,
        branch_id=branch_id
    )