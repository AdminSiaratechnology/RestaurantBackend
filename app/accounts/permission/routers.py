# app/accounts/permission/router.py

from fastapi import (
    APIRouter,
    Depends
)

from app.db.config import SessionDep

from app.accounts.staff.model import (
    StaffRole
)

from app.accounts.permission.schemas import (
    StaffPermissionCreate,
    StaffPermissionUpdate,
    StaffPermissionOut
)

from app.accounts.deps import (
    access_one,
    require_client,
    require_staff_role
)

from app.accounts.permission.services import (
    create_staff_permissions_service,
    update_staff_permissions_service,
    get_staff_permissions_service
)

router = APIRouter(
    prefix="/staff-permissions",
    tags=["Staff Permissions"]
)


# =====================================================
# CREATE
# =====================================================

@router.post(
    "/create",
    response_model=StaffPermissionOut
)
async def create_staff_permissions(
    data: StaffPermissionCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    return await create_staff_permissions_service(
        db,
        data,
        current
    )


# =====================================================
# UPDATE
# =====================================================

@router.put(
    "/{staff_id}",
    response_model=StaffPermissionOut
)
async def update_staff_permissions(
    staff_id: int,
    data: StaffPermissionUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    return await update_staff_permissions_service(
        db,
        staff_id,
        data,
        current
    )


# =====================================================
# STATIC ROUTES
# =====================================================

@router.get("/orders")
async def orders(
    current=Depends(
        require_staff_role(
            StaffRole.waiter
        )
    )
):
    return {
        "message": "Waiter Access"
    }


@router.get("/kitchen")
async def kitchen(
    current=Depends(
        require_staff_role(
            StaffRole.chef
        )
    )
):
    return {
        "message": "Chef Access"
    }


@router.get("/reports")
async def reports(
    current=Depends(
        require_staff_role(
            StaffRole.manager
        )
    )
):
    return {
        "message": "Manager Access"
    }


# =====================================================
# GET STAFF PERMISSIONS
# =====================================================

@router.get(
    "/{staff_id}",
    response_model=StaffPermissionOut
)
async def get_staff_permissions(
    staff_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    return await get_staff_permissions_service(
        db,
        staff_id,
        current
    )