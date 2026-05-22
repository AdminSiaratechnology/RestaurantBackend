from fastapi import APIRouter, Depends, HTTPException
from app.accounts.deps import get_current_user, UserRole
from app.accounts.staff.model import StaffRole

router = APIRouter(
    prefix="/chef",
    tags=["Chef"]
)


# =========================================================
# CHEF DASHBOARD
# =========================================================
@router.get("/dashboard")
async def chef_dashboard(
    current=Depends(get_current_user)
):

    user = current["user"]
    role = current["role"]

    # =====================================================
    # ONLY CHEF ALLOWED
    # =====================================================
    if role != UserRole.STAFF:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    if user.role != StaffRole.chef:
        raise HTTPException(
            status_code=403,
            detail="Chef access only"
        )

    return {
        "role": "chef",

        "permissions": {

            # ✅ ALLOWED
            "manage_kitchen": True,
            "manage_inventory": True,

            # ❌ BLOCKED
            "manage_orders": False,
            "manage_staff": False,
            "manage_customers": False,
            "manage_reports": False,
            "manage_branches": False,
            "access_billing": False,
            "edit_menu_items": False,
            "manage_tables": False
        }
    }

@router.get("/kitchen")
async def kitchen_access(
    current=Depends(get_current_user)
):

    user = current["user"]

    if user.role != StaffRole.chef:
        raise HTTPException(
            status_code=403,
            detail="Chef access only"
        )

    return {
        "message": "Kitchen access granted"
    }


@router.get("/inventory")
async def inventory_access(
    current=Depends(get_current_user)
):

    user = current["user"]

    if user.role != StaffRole.chef:
        raise HTTPException(
            status_code=403,
            detail="Chef access only"
        )

    return {
        "message": "Inventory access granted"
    }