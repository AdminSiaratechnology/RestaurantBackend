from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from passlib.context import CryptContext
from app.accounts.branch.model import Branch
from app.accounts.deps import require_client
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
@router.post("/staff", response_model=StaffOut)
async def create_staff(
    data: StaffCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    # =====================================================
    # ✅ CHECK BRANCH
    # =====================================================
    branch = await db.get(
        Branch,
        data.branch_id
    )

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found"
        )

    # ✅ security check
    if branch.client_id != client.id:
        raise HTTPException(
            status_code=403,
            detail="This branch does not belong to you"
        )

    # =====================================================
    # ✅ CHECK DUPLICATE EMAIL
    # =====================================================
    result = await db.execute(
        select(Staff).where(
            Staff.email == data.email
        )
    )

    existing_staff = result.scalar_one_or_none()

    if existing_staff:
        raise HTTPException(
            status_code=400,
            detail="Staff already exists"
        )

    # =====================================================
    # ✅ CREATE STAFF
    # =====================================================
    staff = Staff(
        name=data.name,
        email=data.email,

        password_hash=pwd_context.hash(
            data.password
        ),

        role=data.role,

        # 🔥 AUTO FROM LOGIN
        client_id=client.id,

        # 🔥 AUTO FROM SELECTED BRANCH
        branch_id=branch.id,

        is_active=True
    )

    db.add(staff)

    await db.commit()

    await db.refresh(staff)

    return staff


# =========================================================
# GET ALL STAFF
# =========================================================
@router.get("/staff", response_model=list[StaffOut])
async def get_all_staff(
    db: SessionDep,
    current=Depends(require_client),
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    is_active: bool | None = None,
    role: StaffRole | None = None
):
    client = current["user"]

    query = select(Staff).where(
        Staff.client_id == client.id
    )

    # ✅ active filter
    if is_active is not None:
        query = query.where(
            Staff.is_active == is_active
        )

    # ✅ role filter
    if role is not None:
        query = query.where(
            Staff.role == role
        )

    # ✅ search filter
    if search:
        query = query.where(
            or_(
                Staff.name.ilike(f"%{search}%"),
                Staff.email.ilike(f"%{search}%")
            )
        )

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)

    staffs = result.scalars().all()

    return staffs


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
@router.put("/staff/{staff_id}", response_model=StaffOut)
async def update_staff(
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
            Staff.client_id == client.id
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
@router.delete("/staff/{staff_id}")
async def delete_staff(
    staff_id: int,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.client_id == client.id
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