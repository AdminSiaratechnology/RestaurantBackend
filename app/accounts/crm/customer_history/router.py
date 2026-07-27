from fastapi import APIRouter

from app.db.config import SessionDep

from app.accounts.crm.customer_history.schema import (
    CustomerVisitCreate,
    CustomerVisitUpdate,
    CustomerVisitOut,
    CustomerVisitAnalytics
)

from app.accounts.crm.customer_history.service import (
    create_customer_visit_service,
    get_customer_visit_service,
    update_customer_visit_service,
    delete_customer_visit_service,
    get_customer_timeline_service,
    get_recent_visits_service,
    get_today_visits_service,
    get_customer_analytics_service,
    get_repeat_customers_service,
    get_inactive_customers_service
)


router = APIRouter(
    prefix="/customer-visits",
    tags=["Customer Visits"]
)


# ==========================================================
# CREATE
# ==========================================================

@router.post(
    "/",
    response_model=CustomerVisitOut
)
async def create_customer_visit(
    payload: CustomerVisitCreate,
    db: SessionDep
):
    return await create_customer_visit_service(
        payload=payload,
        db=db
    )


# ==========================================================
# GET SINGLE
# ==========================================================

@router.get(
    "/{visit_id}",
    response_model=CustomerVisitOut
)
async def get_customer_visit(
    visit_id: int,
    db: SessionDep
):
    return await get_customer_visit_service(
        visit_id=visit_id,
        db=db
    )


# ==========================================================
# UPDATE
# ==========================================================

@router.patch(
    "/{visit_id}",
    response_model=CustomerVisitOut
)
async def update_customer_visit(
    visit_id: int,
    payload: CustomerVisitUpdate,
    db: SessionDep
):
    return await update_customer_visit_service(
        visit_id=visit_id,
        payload=payload,
        db=db
    )


# ==========================================================
# DELETE
# ==========================================================

@router.delete(
    "/{visit_id}"
)
async def delete_customer_visit(
    visit_id: int,
    db: SessionDep
):
    return await delete_customer_visit_service(
        visit_id=visit_id,
        db=db
    )


# ==========================================================
# CUSTOMER TIMELINE
# ==========================================================

@router.get(
    "/customer/{customer_id}"
)
async def customer_timeline(
    customer_id: int,
    db: SessionDep
):
    return await get_customer_timeline_service(
        customer_id=customer_id,
        db=db
    )


# ==========================================================
# RECENT VISITS
# ==========================================================

@router.get(
    "/dashboard/recent"
)
async def recent_visits(
    db: SessionDep,
    limit: int = 20
):
    return await get_recent_visits_service(
        db=db,
        limit=limit
    )


# ==========================================================
# TODAY VISITS
# ==========================================================

@router.get(
    "/dashboard/today"
)
async def today_visits(
    db: SessionDep
):
    return await get_today_visits_service(
        db=db
    )


# ==========================================================
# CUSTOMER ANALYTICS
# ==========================================================

@router.get(
    "/analytics/{customer_id}",
    response_model=CustomerVisitAnalytics
)
async def customer_analytics(
    customer_id: int,
    db: SessionDep
):
    return await get_customer_analytics_service(
        customer_id=customer_id,
        db=db
    )


# ==========================================================
# REPEAT CUSTOMERS
# ==========================================================

@router.get(
    "/reports/repeat-customers"
)
async def repeat_customers(
    db: SessionDep
):
    return await get_repeat_customers_service(
        db=db
    )


# ==========================================================
# INACTIVE CUSTOMERS
# ==========================================================

@router.get(
    "/reports/inactive-customers"
)
async def inactive_customers(
    days: int = 30,
    db: SessionDep = None
):
    return await get_inactive_customers_service(
        days=days,
        db=db
    )