from fastapi import APIRouter, Query, Depends
from datetime import date

from app.db.config import SessionDep
from app.core.cache import Cache

from app.accounts.rep_menu.schema import (
    CategoryDistributionResponse,
    MenuDashboardResponse,
    TopSellingItemsResponse
)

from app.accounts.rep_menu.service import (
    get_category_distribution_all_branches_service,
    get_category_distribution_service,
    dashboard_summary_service,
    get_top_selling_items_all_branches_service,
    get_top_selling_items_service,
    menu_dashboard_all_branches_service
)

router = APIRouter(
    prefix="/reports/menu",
    tags=["Menu Reports"]
)


@router.get(
    "/category-distribution",
    response_model=CategoryDistributionResponse
)
async def get_category_distribution(
    db: SessionDep,
    branch_id: int = Query(...)
):
    today_str = date.today().isoformat()
    cache_key = f"report:{branch_id}:category_distribution:{today_str}"
    cached = await Cache.get(cache_key)
    if cached:
        return CategoryDistributionResponse(**cached)
    result = await get_category_distribution_service(db=db, branch_id=branch_id)
    await Cache.set(cache_key, result if isinstance(result, dict) else result.dict(), expire=21600)
    return result


@router.get(
    "/dashboard-summary",
    response_model=MenuDashboardResponse
)
async def dashboard_summary(
    db: SessionDep,
    branch_id: int
):
    today_str = date.today().isoformat()
    cache_key = f"report:{branch_id}:menu_dashboard:{today_str}"
    cached = await Cache.get(cache_key)
    if cached:
        return MenuDashboardResponse(**cached)
    result = await dashboard_summary_service(db=db, branch_id=branch_id)
    await Cache.set(cache_key, result if isinstance(result, dict) else result.dict(), expire=21600)
    return result


@router.get(
    "/top-selling-items",
    response_model=TopSellingItemsResponse
)
async def get_top_selling_items(
    db: SessionDep,
    branch_id: int = Query(...)
):
    today_str = date.today().isoformat()
    cache_key = f"report:{branch_id}:top_selling:{today_str}"
    cached = await Cache.get(cache_key)
    if cached:
        return TopSellingItemsResponse(**cached)
    result = await get_top_selling_items_service(db=db, branch_id=branch_id)
    await Cache.set(cache_key, result if isinstance(result, dict) else result.dict(), expire=21600)
    return result


from app.accounts.deps import access_four

@router.get(
    "/dashboard-summary/all-branches"
)
async def menu_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await menu_dashboard_all_branches_service(
        db=db,
        current=current
    )



@router.get(
    "/top-selling-items/all-branches"
)
async def get_top_selling_items_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_top_selling_items_all_branches_service(
        db=db,
        current=current
    )


@router.get(
    "/category-distribution/all-branches"
)
async def get_category_distribution_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await get_category_distribution_all_branches_service(
        db=db,
        current=current
    )