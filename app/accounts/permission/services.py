# app/accounts/permission/service.py

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.staff.model import (
    Staff,
    StaffRole
)

from app.accounts.permission.model import (
    StaffPermission
)


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


# =====================================================
# CREATE PERMISSION
# =====================================================

async def create_staff_permissions_service(
    db,
    data,
    current
):
    user = current["user"]

    result = await db.execute(
        select(Staff).where(
            Staff.id == data.staff_id,
            Staff.client_id == user.id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            404,
            "Staff not found"
        )

    if staff.role != StaffRole.manager:
        raise HTTPException(
            400,
            "Custom permissions allowed only for managers"
        )

    result = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == data.staff_id
        )
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Permissions already exist"
        )

    permission = StaffPermission(
        **data.dict()
    )

    db.add(permission)

    await db.commit()
    await db.refresh(permission)

    return permission


# =====================================================
# UPDATE PERMISSION
# =====================================================

async def update_staff_permissions_service(
    db,
    staff_id: int,
    data,
    current
):
    user = current["user"]

    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.client_id == user.id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            404,
            "Staff not found"
        )

    if staff.role != StaffRole.manager:
        raise HTTPException(
            400,
            "Only manager permissions can be updated"
        )

    result = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == staff_id
        )
    )

    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(
            404,
            "Permission not found"
        )

    for key, value in data.dict().items():
        setattr(permission, key, value)

    await db.commit()
    await db.refresh(permission)

    return permission


# =====================================================
# GET STAFF PERMISSIONS
# =====================================================

async def get_staff_permissions_service(
    db,
    staff_id: int,
    current
):
    role = current["role"]
    user = current["user"]

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
            404,
            "Staff not found"
        )

    if staff.role == StaffRole.chef:

        permissions = CHEF_PERMISSIONS.copy()
        permissions["staff_id"] = staff.id

        return permissions

    if staff.role == StaffRole.waiter:

        permissions = WAITER_PERMISSIONS.copy()
        permissions["staff_id"] = staff.id

        return permissions

    result = await db.execute(
        select(StaffPermission).where(
            StaffPermission.staff_id == staff_id
        )
    )

    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(
            404,
            "Permission not found"
        )

    return permission