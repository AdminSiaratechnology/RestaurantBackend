# app/accounts/tax/routers.py

from fastapi import APIRouter, Depends

from app.db.config import SessionDep
from app.accounts.deps import (
    get_current_user,
    access_three
)

from app.accounts.tax.schema import (
    TaxBillingCreate,
    TaxBillingUpdate,
    TaxBillingOut
)

from app.accounts.tax.service import (
    create_tax_settings_service,
    get_tax_settings_service,
    update_tax_settings_service
)

router = APIRouter(
    prefix="/tax_billing",
    tags=["Tax Billing"]
)


@router.post(
    "/",
    response_model=TaxBillingOut
)
async def create_tax_settings(
    data: TaxBillingCreate,
    db: SessionDep,
    current=Depends(access_three)
):
    return await create_tax_settings_service(
        db=db,
        data=data,
        user=current["user"]
    )


@router.get(
    "/{branch_id}",
    response_model=TaxBillingOut
)
async def get_tax_settings(
    branch_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):
    return await get_tax_settings_service(
        db=db,
        branch_id=branch_id,
        user=current["user"]
    )


@router.put(
    "/{branch_id}",
    response_model=TaxBillingOut
)
async def update_tax_settings(
    branch_id: int,
    data: TaxBillingUpdate,
    db: SessionDep,
    current=Depends(access_three)
):
    return await update_tax_settings_service(
        db=db,
        branch_id=branch_id,
        data=data,
        user=current["user"]
    )