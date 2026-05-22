from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from passlib.context import CryptContext
from app.accounts.branch.model import Branch
from app.accounts.deps import require_client, get_current_user, UserRole
from app.accounts.staff.model import Staff, StaffRole
from app.accounts.staff.schemas import (
    StaffCreate,
    StaffOut,
    StaffUpdate
)
from app.db.config import SessionDep


router = APIRouter(
    prefix="/client",
    tags=["Client"]
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)






# =========================================================
# CREATE STAFF
# =========================================================
@router.post(
    "/branches/{branch_id}/staff",
    response_model=StaffOut
)
async def create_staff(
    branch_id: int,
    data: StaffCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    # =====================================================
    # VERIFY BRANCH
    # =====================================================

    branch = await db.get(Branch, branch_id)

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found"
        )

    if branch.client_id != client.id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized branch"
        )

    # =====================================================
    # CHECK DUPLICATE EMAIL INSIDE BRANCH
    # =====================================================

    result = await db.execute(
        select(Staff).where(
            Staff.email == data.email,
            Staff.branch_id == branch_id
        )
    )

    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already exists in this branch"
        )

    # =====================================================
    # CREATE STAFF
    # =====================================================

    staff = Staff(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        role=data.role,

        client_id=client.id,
        branch_id=branch_id,

        is_active=True
    )

    db.add(staff)

    await db.commit()
    await db.refresh(staff)

    return staff


# =========================================================
# GET ALL STAFF
# =========================================================
@router.get(
    "/branches/{branch_id}/staff",
    response_model=list[StaffOut]
)
async def get_staff_by_branch(
    branch_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):

    user = current["user"]
    role = current["role"]

    # =====================================================
    # STAFF SECURITY
    # =====================================================

    if role == UserRole.STAFF:

        if user.branch_id != branch_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

    # =====================================================
    # CLIENT SECURITY
    # =====================================================

    elif role == UserRole.CLIENT:

        branch = await db.get(Branch, branch_id)

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Branch not found"
            )

        if branch.client_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

    # =====================================================
    # QUERY
    # =====================================================

    result = await db.execute(
        select(Staff).where(
            Staff.branch_id == branch_id
        )
    )

    return result.scalars().all()

# =========================================================
# SEARCH STAFF
# =========================================================
# @router.get("/staff/search", response_model=list[StaffOut])
# async def search_staff(
#     name: str,
#     db: SessionDep,
#     current=Depends(require_client)
# ):
#     client = current["user"]

#     query = select(Staff).where(
#         Staff.client_id == client.id,
#         Staff.name.ilike(f"%{name}%")
#     )

#     result = await db.execute(query)

#     staffs = result.scalars().all()

#     return staffs


# =========================================================
# UPDATE STAFF
# =========================================================
@router.put("/branches/{branch_id}/staff/{staff_id}")
async def update_staff(
    branch_id: int,
    staff_id: int,
    data: StaffUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    # =====================================================
    # ✅ GET STAFF
    # =====================================================
    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.branch_id == branch_id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    # =====================================================
    # ✅ UPDATE NAME
    # =====================================================
    if data.name is not None:
        staff.name = data.name

    # =====================================================
    # ✅ UPDATE EMAIL
    # =====================================================
    if data.email is not None:

        email_check = await db.execute(
            select(Staff.id).where(
                Staff.email == data.email,
                Staff.id != staff_id
            )
        )

        existing_email = email_check.scalar_one_or_none()

        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Email already exists"
            )

        staff.email = data.email

    # =====================================================
    # ✅ UPDATE PASSWORD
    # =====================================================
    if data.password is not None:
        staff.password_hash = pwd_context.hash(
            data.password
        )

    # =====================================================
    # ✅ UPDATE ROLE
    # =====================================================
    if data.role is not None:
        staff.role = data.role

    # =====================================================
    # ✅ UPDATE BRANCH
    # =====================================================
    if data.branch_id is not None:

        branch = await db.get(
            Branch,
            data.branch_id
        )

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Branch not found"
            )

        # ✅ SECURITY CHECK
        if branch.client_id != client.id:
            raise HTTPException(
                status_code=403,
                detail="This branch does not belong to you"
            )

        # ✅ UPDATE BRANCH
        staff.branch_id = branch.id

    # =====================================================
    # ✅ UPDATE ACTIVE STATUS
    # =====================================================
    if data.is_active is not None:
        staff.is_active = data.is_active

    # =====================================================
    # ✅ SAVE
    # =====================================================
    await db.commit()

    await db.refresh(staff)

    return staff


# =========================================================
# DELETE STAFF
# =========================================================
@router.delete("/branches/{branch_id}/staff/{staff_id}")
async def delete_staff(
    branch_id: int,
    staff_id: int,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.branch_id == branch_id
        )
    )
    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    await db.delete(staff)

    await db.commit()

    return {
        "message": "Staff deleted successfully"
    }