from fastapi import APIRouter, Depends

from app.db.config import SessionDep
from app.accounts.deps import access_one

from app.accounts.legaldetails.schema import (
    LegalComplianceCreate,
    LegalComplianceResponse
)

from app.accounts.legaldetails.service import (
    LegalComplianceService
)

router = APIRouter(
    prefix="/legal_compliance",
    tags=["Legal Compliance"]
)


@router.post(
    "/create-update",
    response_model=LegalComplianceResponse
)
async def create_update_legal_compliance(
    payload: LegalComplianceCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    return await LegalComplianceService.create_or_update(
        db,
        payload
    )


@router.get(
    "/{branch_id}",
    response_model=LegalComplianceResponse
)
async def get_legal_compliance(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    return await LegalComplianceService.get_by_branch(
        db,
        branch_id
    )


@router.put(
    "/update/{branch_id}",
    response_model=LegalComplianceResponse
)
async def update_legal_compliance(
    branch_id: int,
    payload: LegalComplianceCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    return await LegalComplianceService.update(
        db,
        branch_id,
        payload
    )


@router.delete(
    "/delete/{branch_id}"
)
async def delete_legal_compliance(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    return await LegalComplianceService.delete(
        db,
        branch_id
    )