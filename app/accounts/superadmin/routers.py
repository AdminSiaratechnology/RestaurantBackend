from fastapi import APIRouter, Depends

from app.db.config import SessionDep

from app.accounts.deps import (
    require_super_admin
)

from app.accounts.superadmin.schemas import (
    SuperAdminCreate,
    SuperAdminOut,
    SuperAdminUpdate,
    PartnerCreate,
    PartnerOut
)

from app.accounts.superadmin.services import (
    create_superadmin_service,
    get_superadmin_service,
    update_superadmin_service,
    create_partner_service,
    update_partner_service,
    get_all_partners_service,
    delete_partner_service,
    activate_partner_service
)

router = APIRouter(
    prefix="/superadmin",
    tags=["Super Admin"]
)


@router.post(
    "/create",
    response_model=SuperAdminOut
)
async def create_superadmin(
    data: SuperAdminCreate,
    db: SessionDep
):
    return await create_superadmin_service(
        db=db,
        data=data
    )


@router.get(
    "/",
    response_model=SuperAdminOut
)
async def get_superadmin(
    db: SessionDep,
    current=Depends(
        require_super_admin
    )
):
    return await get_superadmin_service(
        db=db
    )


@router.put(
    "/update",
    response_model=SuperAdminOut
)
async def update_superadmin(
    data: SuperAdminUpdate,
    db: SessionDep,
    current=Depends(
        require_super_admin
    )
):
    return await update_superadmin_service(
        db=db,
        data=data
    )


@router.post(
    "/partners",
    response_model=PartnerOut
)
async def create_partner(
    data: PartnerCreate,
    db: SessionDep,
    current=Depends(
        require_super_admin
    )
):
    return await create_partner_service(
        db=db,
        data=data
    )


@router.put(
    "/partners/{partner_id}",
    response_model=PartnerOut
)
async def update_partner(
    partner_id: int,
    data: PartnerCreate,
    db: SessionDep,
    current=Depends(
        require_super_admin
    )
):
    return await update_partner_service(
        db=db,
        partner_id=partner_id,
        data=data
    )


@router.get(
    "/partners",
    response_model=list[PartnerOut]
)
async def get_all_partners(
    db: SessionDep,
    current=Depends(
        require_super_admin
    ),
    skip: int = 0,
    limit: int = 10
):
    return await get_all_partners_service(
        db=db,
        skip=skip,
        limit=limit
    )


@router.delete(
    "/partners/{partner_id}"
)
async def delete_partner(
    partner_id: int,
    db: SessionDep,
    current=Depends(
        require_super_admin
    )
):
    return await delete_partner_service(
        db=db,
        partner_id=partner_id
    )


@router.put(
    "/partners/{partner_id}/activate"
)
async def activate_partner(
    partner_id: int,
    db: SessionDep,
    current=Depends(
        require_super_admin
    )
):
    return await activate_partner_service(
        db=db,
        partner_id=partner_id
    )