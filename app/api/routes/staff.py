from fastapi import APIRouter, Depends
from app.accounts.deps import require_staff
from app.accounts.staff.model import Staff
from app.accounts.staff.schemas import StaffUpdate
from app.db.config import SessionDep

router = APIRouter(prefix="/staff", tags=["Staff"])


@router.get("/me")
async def get_my_profile(current=Depends(require_staff)):
    return current["user"]


from fastapi import HTTPException
from sqlalchemy import select
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.put("/me")
async def update_my_profile(
    data: StaffUpdate,
    db: SessionDep,
    current=Depends(require_staff)
):
    staff = current["user"]  # 🔥 THIS IS LOGGED-IN STAFF

    # ✅ Update name
    if data.name is not None:
        staff.name = data.name

    # ✅ Update email (with duplicate check)
    if data.email is not None:
        result = await db.execute(
            select(Staff).where(
                Staff.email == data.email,
                Staff.id != staff.id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(400, "Email already in use")

        staff.email = data.email

    # ✅ Update password
    if data.password is not None:
        staff.password_hash = pwd_context.hash(data.password)

    await db.commit()
    await db.refresh(staff)

    return {
        "message": "Profile updated successfully",
        "data": staff
    }