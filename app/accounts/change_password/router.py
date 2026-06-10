# app/accounts/change_password/router.py

from fastapi import APIRouter, Depends, HTTPException
from app.accounts.change_password.schema import (
    ChangePasswordRequest,
    ChangePasswordResponse
)

from app.accounts.auth.utils import (
    verify_password,
    hash_password
)

from app.accounts.deps import get_current_user
from app.db.config import SessionDep

router = APIRouter(
    prefix="/change_password",
    tags=["Change Password"]
)


@router.put(
    "/change-password",
    response_model=ChangePasswordResponse
)
async def change_password(
    data: ChangePasswordRequest,
    db: SessionDep,
    current=Depends(get_current_user)
):
    user = current["user"]

    # Verify current password
    if not verify_password(
        data.current_password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    # Prevent same password
    if verify_password(
        data.new_password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password"
        )

    try:
        user.password_hash = hash_password(
            data.new_password
        )

        await db.commit()
        await db.refresh(user)

        return ChangePasswordResponse(
            success=True,
            message="Password changed successfully"
        )

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to change password"
        )