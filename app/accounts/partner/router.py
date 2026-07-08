# app/accounts/partner/router.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from app.db.config import SessionDep
from app.accounts.client.schema import (
    ClientOut,
    ClientCreate,
    ClientUpdate
)

from app.accounts.deps import (
    access_two
)

from app.accounts.partner.service import (
    create_client_service,
    get_my_clients_service,
    update_client_service,
    delete_client_service,
    activate_client_service
)

router = APIRouter(
    prefix="/partner",
    tags=["Partner"]
)


@router.post(
    "/clients",
    response_model=ClientOut
)
async def create_client(
    data: ClientCreate,
    db: SessionDep,
    request: Request,
    current=Depends(access_two)
):
    return await create_client_service(
        db,
        data,
        current,
        request,
    )


@router.get(
    "/clients",
    response_model=list[ClientOut]
)
async def get_my_clients(
    db: SessionDep,
    current=Depends(access_two),
    partner_id: int | None = None
):
    return await get_my_clients_service(
        db,
        current,
        partner_id
    )


@router.put(
    "/clients/{client_id}",
    response_model=ClientOut
)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    db: SessionDep,
    request: Request,
    current=Depends(access_two)
):
    return await update_client_service(
        db,
        client_id,
        data,
        current,
        request,
    )


@router.delete(
    "/clients/{client_id}"
)
async def delete_client(
    client_id: int,
    db: SessionDep,
    request: Request,
    current=Depends(access_two)
):
    return await delete_client_service(
        db,
        client_id,
        current,
        request,
    )


@router.put(
    "/clients/{client_id}/activate"
)
async def activate_client(
    client_id: int,
    db: SessionDep,
    request: Request,
    current=Depends(access_two)
):
    return await activate_client_service(
        db,
        client_id,
        current,
        request,
    )



# app/accounts/partner/router.py

from app.accounts.partner.service import (
    partner_dashboard_service
)
from app.accounts.partner.schema import (
    PartnerDashboardOut
)


@router.get(
    "/dashboard",
    response_model=PartnerDashboardOut
)
async def partner_dashboard(
    db: SessionDep,
    current=Depends(access_two),
    partner_id: int | None = None
):
    return await partner_dashboard_service(
        db,
        current,
        partner_id
    )