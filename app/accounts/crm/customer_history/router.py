"""
app/accounts/crm/customer_history/router.py
"""

from typing import List, Optional

from fastapi import APIRouter, Query

from app.db.config import SessionDep

from app.accounts.crm.customer_history import service

from app.accounts.crm.customer_history.schema import (
    VisitHistoryOut,
    VisitHistoryStatsOut,
)


router = APIRouter(
    prefix="/customer-visits",
    tags=["Customer Visits"],
)


# ==========================================================
# LIST CUSTOMER VISITS
# ==========================================================

@router.get(
    "",
    response_model=List[VisitHistoryOut],
)
async def list_visit_history(
    db: SessionDep,

    customer_id: Optional[int] = Query(
        default=None,
    ),

    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),

    offset: int = Query(
        default=0,
        ge=0,
    ),
):

    return await service.get_customer_visits(
        db=db,
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )


# ==========================================================
# CUSTOMER VISIT STATS
# ==========================================================

@router.get(
    "/stats",
    response_model=VisitHistoryStatsOut,
)
async def visit_history_stats(
    customer_id: int,
    db: SessionDep,
):

    return await service.get_visit_stats(
        db=db,
        customer_id=customer_id,
    )