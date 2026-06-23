# app/accounts/reports/router.py

from app.accounts.deps import require_client, access_one
from fastapi import APIRouter, Depends
from datetime import date

from app.db.config import SessionDep
from app.accounts.rep_payment.service import (
    payment_method_totals_all_branches_service,
    payment_method_totals_service,
    payment_report_service,
    payment_report_all_branches_service
)

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


@router.get("/payments")
async def payment_report(
    db: SessionDep,
    branch_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    return await payment_report_service(
        db=db,
        branch_id=branch_id,
        from_date=from_date,
        to_date=to_date,
    )



# app/accounts/reports/router.py

@router.get("/payments/all-branches")
async def payment_report_all_branches(
    db: SessionDep,
    current=Depends(require_client),
    from_date: date | None = None,
    to_date: date | None = None,
):
    return await payment_report_all_branches_service(
        db=db,
        client_id=current["user"].id,
        from_date=from_date,
        to_date=to_date,
    )



@router.get("/payments/method-totals")
async def payment_method_totals(
    db: SessionDep,
    branch_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    return await payment_method_totals_service(
        db=db,
        branch_id=branch_id,
        from_date=from_date,
        to_date=to_date,
    )

@router.get("/payments/method-totals/all-branches")
async def payment_method_totals_all_branches(
    db: SessionDep,
    current=Depends(require_client),
    from_date: date | None = None,
    to_date: date | None = None,
):
    return await payment_method_totals_all_branches_service(
        db=db,
        client_id=current["user"].id,
        from_date=from_date,
        to_date=to_date,
    )