from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from passlib.context import CryptContext
from app.accounts.branch.model import Branch
from app.accounts.deps import require_client, get_current_user, UserRole
from app.accounts.staff.model import Staff, StaffRole
from app.accounts.staff.schemas import (
    StaffCreate,
    StaffOut,
    StaffUpdate,
    StaffSalaryBankUpdate

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

    branch = await db.get(Branch, branch_id)

    if not branch:
        raise HTTPException(404, "Branch not found")

    if branch.client_id != client.id:
        raise HTTPException(403, "Unauthorized branch")

    # Global email check
    result = await db.execute(
        select(Staff).where(
            Staff.email == data.email
        )
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Email already exists"
        )

    print("CREATE STAFF:", data.model_dump())

    staff = Staff(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(data.password),

        role=data.role,
        gender=data.gender,
        phone_number=data.phone_number,

        client_id=client.id,
        branch_id=branch_id,
        is_active=True,

        street_address=data.street_address,
        city=data.city,
        state=data.state,
        pincode=data.pincode,

        monthly_salary=data.monthly_salary,
        hourly_rate=data.hourly_rate,

        aadhaar_number=data.aadhaar_number,
        pan_number=data.pan_number,

        bank_account=data.bank_account,
        ifsc_code=data.ifsc_code,
        bank_name=data.bank_name
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
@router.put(
    "/branches/{branch_id}/staff/{staff_id}",
    response_model=StaffOut
)
async def update_staff(
    branch_id: int,
    staff_id: int,
    data: StaffUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    branch = await db.get(Branch, branch_id)

    if not branch:
        raise HTTPException(404, "Branch not found")

    if branch.client_id != client.id:
        raise HTTPException(403, "Unauthorized")

    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.branch_id == branch_id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(404, "Staff not found")

    if data.name is not None:
        staff.name = data.name

    if data.email is not None:

        email_check = await db.execute(
            select(Staff.id).where(
                Staff.email == data.email,
                Staff.id != staff_id
            )
        )

        if email_check.scalar_one_or_none():
            raise HTTPException(
                400,
                "Email already exists"
            )

        staff.email = data.email

    if data.password is not None:
        staff.password_hash = pwd_context.hash(
            data.password
        )

    if data.role is not None:
        staff.role = data.role

    if data.gender is not None:
        staff.gender = data.gender

    if data.phone_number is not None:
        staff.phone_number = data.phone_number

    if data.is_active is not None:
        staff.is_active = data.is_active

    if data.street_address is not None:
        staff.street_address = data.street_address

    if data.city is not None:
        staff.city = data.city

    if data.state is not None:
        staff.state = data.state

    if data.pincode is not None:
        staff.pincode = data.pincode

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

    branch = await db.get(Branch, branch_id)

    if not branch:
        raise HTTPException(404, "Branch not found")

    if branch.client_id != client.id:
        raise HTTPException(403, "Unauthorized")

    result = await db.execute(
        select(Staff).where(
            Staff.id == staff_id,
            Staff.branch_id == branch_id
        )
    )

    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(404, "Staff not found")

    await db.delete(staff)
    await db.commit()

    return {
        "message": "Staff deleted successfully"
    }


@router.put(
    "/branches/{branch_id}/staff/{staff_id}/salary-bank",
    response_model=StaffOut
)
async def update_staff_salary_bank(
    branch_id: int,
    staff_id: int,
    data: StaffSalaryBankUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    branch = await db.get(Branch, branch_id)

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found"
        )

    if branch.client_id != client.id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized"
        )

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

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(staff, field, value)

    await db.commit()
    await db.refresh(staff)

    return staff