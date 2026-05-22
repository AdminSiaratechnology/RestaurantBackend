
# app/accounts/staff_permission/router.py
from app.accounts.staff.model import Staff, StaffRole
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.deps import access_one,UserRole, require_staff_role 
from app.db.config import SessionDep
from app.accounts.staff.model import Staff
from app.accounts.permission.model import StaffPermission
from app.accounts.permission.schemas import (
    StaffPermissionCreate,
    StaffPermissionUpdate,
    StaffPermissionOut
)

from app.accounts.deps import require_client

router = APIRouter(
    prefix="/staff-permissions",
    tags=["Staff Permissions"]
)




@router.put("/{staff_id}", response_model=StaffPermissionOut)
async def update_staff_permissions(
    staff_id: int,
    data: StaffPermissionUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    user = current["user"]

    # ✅ Check staff ownership
    staff_result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.client_id == user.id
        )
    )

    staff = staff_result.scalar_one_or_none()

    if not staff:
        raise HTTPException(404, "Staff not found")

    # ✅ Get permission
    result = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == staff_id
        )
    )

    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(404, "Permission not found")

    # ✅ Update fields
    for key, value in data.dict().items():
        setattr(permission, key, value)

    await db.commit()
    await db.refresh(permission)

    return permission




@router.get("/{staff_id}", response_model=StaffPermissionOut)
async def get_staff_permissions(
    staff_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    # ✅ Verify staff access
    staff_query = select(Staff).where(Staff.id == staff_id)
    if role.value == "client":
        staff_query = staff_query.where(Staff.client_id == user.id)
    elif role.value == "staff":
        staff_query = staff_query.where(Staff.id == user.id)
    
    staff_result = await db.execute(staff_query)
    staff = staff_result.scalar_one_or_none()

    if not staff:
        raise HTTPException(404, "Staff not found")

    # ✅ If chef, return default kitchen & inventory permissions
    if staff.role == StaffRole.chef:
        return {
            "staff_id": staff_id,
            "manage_orders": False,
            "manage_staff": False,
            "manage_inventory": True,
            "manage_customers": False,
            "manage_reports": False,
            "manage_branches": False,
            "access_billing": False,
            "edit_menu_items": False,
            "manage_tables": False,
            "manage_kitchen": True
        }

    # ✅ Otherwise check DB
    result = await db.execute(
        select(StaffPermission).where(StaffPermission.staff_id == staff_id)
    )
    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(404, "Permission not found")

    return permission


@router.get("/chef/{staff_id}", response_model=StaffPermissionOut)
async def get_chef_default_permissions(
    staff_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    # This is a dedicated API that returns fixed Chef permissions
    return {
        "staff_id": staff_id,
        "manage_orders": False,
        "manage_staff": False,
        "manage_inventory": True,
        "manage_customers": False,
        "manage_reports": False,
        "manage_branches": False,
        "access_billing": False,
        "edit_menu_items": False,
        "manage_tables": False,
        "manage_kitchen": True
    }



@router.post("/create", response_model=StaffPermissionOut)
async def create_staff_permissions(
    data: StaffPermissionCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    user = current["user"]

    # ✅ Check staff belongs to client
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

    # ✅ Only managers can receive permissions
    if staff.role != StaffRole.manager:
        raise HTTPException(
            status_code=400,
            detail="Permissions can only be assigned to managers"
        )

    # ✅ Prevent duplicate permissions
    existing = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == data.staff_id
        )
    )

    existing_permission = existing.scalar_one_or_none()

    if existing_permission:
        raise HTTPException(
            status_code=400,
            detail="Permissions already created for this staff"
        )

    # ✅ Create permission
    permission = StaffPermission(
        **data.dict()
    )

    db.add(permission)

    await db.commit()
    await db.refresh(permission)

    return permission




@router.get("/orders")
async def orders(
    current=Depends(
        require_staff_role(StaffRole.waitr)
    )
):
    return {"message": "Waiter Access"}


@router.get("/kitchen")
async def kitchen(
    current=Depends(
        require_staff_role(StaffRole.chef)
    )
):
    return {"message": "Chef Access"}


@router.get("/reports")
async def reports(
    current=Depends(
        require_staff_role(StaffRole.manager)
    )
):
    return {"message": "Manager Access"}