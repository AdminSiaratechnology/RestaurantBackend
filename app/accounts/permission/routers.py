from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.staff.model import Staff, StaffRole
from app.accounts.permission.model import StaffPermission
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
from app.db.config import SessionDep


router = APIRouter(
    prefix="/staff-permissions",
    tags=["Staff Permissions"]
)


# =========================================================
# DEFAULT ROLE PERMISSIONS
# =========================================================

CHEF_PERMISSIONS = {
    "staff_id": 0,
    "manage_orders": False,
    "manage_staff": False,
    "manage_inventory": True,
    "manage_customers": False,
    "manage_reports": False,
    "manage_branches": False,
    "access_billing": False,
    "edit_menu_items": False,
    "manage_tables": False,
    "manage_kitchen": True,
    "manage_offers": False,
    "manage_brands": False
}


WAITER_PERMISSIONS = {
    "staff_id": 0,
    "manage_orders": True,
    "manage_staff": False,
    "manage_inventory": False,
    "manage_customers": True,
    "manage_reports": False,
    "manage_branches": False,
    "access_billing": True,
    "edit_menu_items": False,
    "manage_tables": True,
    "manage_kitchen": False,
    "manage_offers": False,
    "manage_brands": False
}


# =========================================================
# CREATE STAFF PERMISSIONS
# =========================================================

@router.post("/create", response_model=StaffPermissionOut)
async def create_staff_permissions(
    data: StaffPermissionCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    user = current["user"]

    # ✅ Verify staff belongs to client
    result = await db.execute(
        select(Staff).where(
            Staff.id == data.staff_id,
            Staff.client_id == user.id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    # ✅ Only managers can receive custom permissions
    if staff.role != StaffRole.manager:
        raise HTTPException(
            status_code=400,
            detail="Custom permissions allowed only for managers"
        )

    # ✅ Prevent duplicate permission creation
    existing = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == data.staff_id
        )
    )

    existing_permission = existing.scalar_one_or_none()

    if existing_permission:
        raise HTTPException(
            status_code=400,
            detail="Permissions already exist"
        )

    # ✅ Create permission
    permission = StaffPermission(
        **data.dict()
    )

    db.add(permission)

    await db.commit()
    await db.refresh(permission)

    return permission


# =========================================================
# UPDATE STAFF PERMISSIONS
# =========================================================

@router.put("/{staff_id}", response_model=StaffPermissionOut)
async def update_staff_permissions(
    staff_id: int,
    data: StaffPermissionUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    user = current["user"]

    # ✅ Verify staff ownership
    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.client_id == user.id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    # ✅ Only managers can have editable permissions
    if staff.role != StaffRole.manager:
        raise HTTPException(
            status_code=400,
            detail="Only manager permissions can be updated"
        )

    # ✅ Fetch permission
    result = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == staff_id
        )
    )

    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(
            status_code=404,
            detail="Permission not found"
        )

    # ✅ Update fields
    for key, value in data.dict().items():
        setattr(permission, key, value)

    await db.commit()
    await db.refresh(permission)

    return permission


# =========================================================
# GET STAFF PERMISSIONS
# =========================================================

@router.get("/{staff_id}", response_model=StaffPermissionOut)
async def get_staff_permissions(
    staff_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    # ✅ Verify access
    query = select(Staff).where(
        Staff.id == staff_id
    )

    if role.value == "client":
        query = query.where(
            Staff.client_id == user.id
        )

    elif role.value == "staff":
        query = query.where(
            Staff.id == user.id
        )

    result = await db.execute(query)

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    # =====================================================
    # CHEF DEFAULT PERMISSIONS
    # =====================================================

    if staff.role == StaffRole.chef:

        permissions = CHEF_PERMISSIONS.copy()
        permissions["staff_id"] = staff.id

        return permissions

    # =====================================================
    # WAITER DEFAULT PERMISSIONS
    # =====================================================

    if staff.role == StaffRole.waitr:

        permissions = WAITER_PERMISSIONS.copy()
        permissions["staff_id"] = staff.id

        return permissions

    # =====================================================
    # MANAGER CUSTOM PERMISSIONS
    # =====================================================

    result = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == staff_id
        )
    )

    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(
            status_code=404,
            detail="Permission not found"
        )

    return permission


# ✅ STATIC ROUTES FIRST

@router.get("/orders")
async def orders(
    current=Depends(
        require_staff_role(StaffRole.waitr)
    )
):
    return {
        "message": "Waiter Access"
    }


@router.get("/kitchen")
async def kitchen(
    current=Depends(
        require_staff_role(StaffRole.chef)
    )
):
    return {
        "message": "Chef Access"
    }


@router.get("/reports")
async def reports(
    current=Depends(
        require_staff_role(StaffRole.manager)
    )
):
    return {
        "message": "Manager Access"
    }


# ✅ DYNAMIC ROUTES AFTER STATIC ROUTES

@router.get("/{staff_id}", response_model=StaffPermissionOut)
async def get_staff_permissions(
    staff_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    ...