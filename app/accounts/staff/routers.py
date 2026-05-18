# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy import select
# from app.accounts.table.router import access_table, UserRole
# from app.db.config import SessionDep
# from app.accounts.staff.model import Staff
# from app.accounts.staff.schemas import StaffCreate, StaffOut, StaffUpdate
# from app.accounts.deps import (
#     # require_roles,
#     # UserRole,
#     get_tenant_if_accessible,
#     access_one,UserRole
# )
# from passlib.context import CryptContext

# router = APIRouter(prefix="/staff", tags=["Staff"])

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# # staff_access = require_roles(
# #     UserRole.SUPER_ADMIN,
# #     UserRole.ADMIN
# # )




# @router.post("/tenants/{tenant_id}", response_model=StaffOut)
# async def create_staff(
#     tenant_id: int,
#     data: StaffCreate,
#     db: SessionDep,
#     current=Depends(access_table)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     tenant = await get_tenant_if_accessible(
#         db, tenant_id, role, user
#     )

#     # 🔍 Duplicate email check
#     result = await db.execute(
#         select(Staff).where(Staff.email == data.email)
#     )
#     if result.scalar_one_or_none():
#         raise HTTPException(400, "Staff already exists")

#     staff = Staff(
#         name=data.name,
#         email=data.email,
#         password_hash=pwd_context.hash(data.password),
#         role="staff",
#         tenant_id=tenant.id,
#         is_active=True
#     )

#     db.add(staff)
#     await db.commit()
#     await db.refresh(staff)

#     return staff





# @router.get("/tenants/{tenant_id}", response_model=list[StaffOut])
# async def get_staffs(
#     tenant_id: int,
#     db: SessionDep,
#     current=Depends(access_one)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     await get_tenant_if_accessible(
#         db, tenant_id, role, user
#     )

#     result = await db.execute(
#         select(Staff).where(Staff.tenant_id == tenant_id)
#     )

#     return result.scalars().all()




# @router.get("/{staff_id}", response_model=StaffOut)
# async def get_staff(
#     staff_id: int,
#     db: SessionDep,
#     current=Depends(access_table)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     result = await db.execute(
#         select(Staff).where(Staff.id == staff_id)
#     )
#     staff = result.scalar_one_or_none()

#     if not staff:
#         raise HTTPException(404, "Staff not found")

#     return staff




# @router.delete("/{staff_id}")
# async def delete_staff(
#     staff_id: int,
#     db: SessionDep,
#     current=Depends(access_table)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     result = await db.execute(
#         select(Staff).where(Staff.id == staff_id)
#     )
#     staff = result.scalar_one_or_none()

#     if not staff:
#         raise HTTPException(404, "Staff not found")

#     await get_tenant_if_accessible(
#         db, staff.tenant_id, role, user
#     )

#     await db.delete(staff)
#     await db.commit()

#     return {"message": "Staff deleted"}



