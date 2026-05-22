from fastapi import APIRouter, Depends, HTTPException
from app.accounts.deps import get_current_user, UserRole
from app.accounts.staff.model import StaffRole

router = APIRouter(
    prefix="/waiter",
    tags=["Waiter"]
)


# =========================================================
# WAITER DASHBOARD
# =========================================================
@router.get("/dashboard")
async def waiter_dashboard(
    current=Depends(get_current_user)
):

    user = current["user"]
    role = current["role"]

    # =====================================================
    # ONLY STAFF
    # =====================================================
    if role != UserRole.STAFF:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    # =====================================================
    # ONLY WAITER
    # =====================================================
    if user.role != StaffRole.waitr:
        raise HTTPException(
            status_code=403,
            detail="Waiter access only"
        )

    return {

        "role": "waiter",

        "permissions": {

            # ✅ ALLOWED
            "view_menu": True,
            "view_order_status": True,
            "manage_orders": True,
            "manage_tables": True,

            # ❌ BLOCKED
            "manage_staff": False,
            "manage_inventory": False,
            "manage_customers": False,
            "manage_reports": False,
            "manage_branches": False,
            "access_billing": False,
            "edit_menu_items": False,
            "manage_kitchen": False
        }
    }

@router.get("/menu")
async def waiter_menu(
    current=Depends(get_current_user)
):

    user = current["user"]

    if user.role != StaffRole.waitr:
        raise HTTPException(
            status_code=403,
            detail="Waiter access only"
        )

    return {
        "message": "Menu access granted"
    }


@router.get("/orders/status")
async def order_status(
    current=Depends(get_current_user)
):

    user = current["user"]

    if user.role != StaffRole.waitr:
        raise HTTPException(
            status_code=403,
            detail="Waiter access only"
        )

    return {
        "message": "Order status access granted"
    }


@router.get("/tables")
async def waiter_tables(
    current=Depends(get_current_user)
):

    user = current["user"]

    if user.role != StaffRole.waitr:
        raise HTTPException(
            status_code=403,
            detail="Waiter access only"
        )

    return {
        "message": "Table access granted"
    }


@router.post("/orders")
async def place_order(
    current=Depends(get_current_user)
):

    user = current["user"]

    if user.role != StaffRole.waitr:
        raise HTTPException(
            status_code=403,
            detail="Waiter access only"
        )

    return {
        "message": "Order placement allowed"
    }