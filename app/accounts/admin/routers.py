# from sqlalchemy import or_, select
# from fastapi import APIRouter, Depends, HTTPException, Path, Query
# from passlib.context import CryptContext
# from app.accounts.deps import get_current_user, get_tenant_if_accessible,  require_admin, require_roles
# from app.accounts.enum import UserRole
# from app.accounts.partner.model import Partner
# from app.accounts.staff.model import Staff
# from app.accounts.staff.schemas import StaffCreate, StaffOut, StaffUpdate
# from app.db.config import SessionDep
# from app.accounts.admin.model import Admin
# from app.accounts.tenant.model import Tenant
# from app.accounts.admin.schema import AdminOut, AdminUpdate
# from app.accounts.tenant.schemas import TenantOut, TenantCreate, TenantUpdate
# from slugify import slugify
# from app.accounts.deps import access_three,UserRole
# # from app.accounts.deps import require_roles, UserRole


# router = APIRouter(prefix="/admin", tags=["Admin"])

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# # admin_access = require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)


# @router.put("/me", response_model=AdminOut)
# async def update_my_profile(
#     data: AdminUpdate,
#     db: SessionDep,
#     current=Depends(require_admin)
# ):
#     admin = current["user"]

#     # 🧠 Update fields
#     if data.name is not None:
#         admin.name = data.name

#     if data.email is not None:
#         result = await db.execute(
#             select(Admin).where(Admin.email == data.email, Admin.id != admin.id)
#         )
#         if result.scalar_one_or_none():
#             raise HTTPException(400, "Email already in use")

#         admin.email = data.email

#     if data.password is not None:
#         admin.password_hash = pwd_context.hash(data.password)

#     if data.is_active is not None:
#         admin.is_active = data.is_active

#     await db.commit()
#     await db.refresh(admin)

#     return admin




# @router.delete("/tenants/{tenant_id}")
# async def delete_tenant(
#     tenant_id: int,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     tenant = await get_tenant_if_accessible(
#         tenant_id=tenant_id,   # ✅ correct
#         db=db,
#         current=current
#     )

#     await db.delete(tenant)
#     await db.commit()

#     return {"message": "Tenant deleted"}

# @router.post("/tenants", response_model=TenantOut)
# async def create_tenant(
#     data: TenantCreate,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     # 🔥 Decide admin_id safely
#     if role == UserRole.ADMIN:
#         admin_id = user.id

#     elif role == UserRole.PARTNER:
#         if not hasattr(data, "admin_id") or not data.admin_id:
#             raise HTTPException(400, "admin_id required")

#         # ✅ check admin belongs to this partner
#         result = await db.execute(
#             select(Admin).where(
#                 Admin.id == data.admin_id,
#                 Admin.partner_id == user.id
#             )
#         )
#         admin = result.scalar_one_or_none()

#         if not admin:
#             raise HTTPException(403, "Admin not under this partner")

#         admin_id = data.admin_id

#     elif role == UserRole.SUPER_ADMIN:
#         if not hasattr(data, "admin_id") or not data.admin_id:
#             raise HTTPException(400, "admin_id required")

#         admin = await db.get(Admin, data.admin_id)
#         if not admin:
#             raise HTTPException(404, "Admin not found")

#         admin_id = data.admin_id

#     # 🔥 slug duplicate check
#     result = await db.execute(
#         select(Tenant).where(Tenant.slug == data.slug)
#     )
#     if result.scalar_one_or_none():
#         raise HTTPException(400, "Slug already exists")

#     tenant = Tenant(
#         name=data.name,
#         slug=data.slug,
#         admin_id=admin_id
#     )

#     db.add(tenant)
#     await db.commit()
#     await db.refresh(tenant)

#     return tenant

# # @router.post("/tenants", response_model=TenantOut)
# # async def create_tenant(
# #     data: TenantCreate,
# #     db: SessionDep,
# #     current=Depends(access_three)
# # ):
# #     admin = current["user"]

# #     slug = slugify(data.slug)

# #     # 🔥 FIX: check slug uniqueness
# #     result = await db.execute(
# #         select(Tenant).where(Tenant.slug == slug)
# #     )
# #     if result.scalar_one_or_none():
# #         raise HTTPException(400, "Slug already exists")

# #     tenant = Tenant(
# #         name=data.name,
# #         slug=slug,
# #         admin_id=admin.id
# #     )

# #     db.add(tenant)
# #     await db.commit()
# #     await db.refresh(tenant)

# #     return tenant


# @router.put("/tenants/{tenant_id}", response_model=TenantOut)
# async def update_tenant(
#     tenant_id: int,
#     data: TenantUpdate,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     tenant = await get_tenant_if_accessible(
#         tenant_id=tenant_id,   # ✅ FIXED
#         db=db,
#         current=current
#     )

#     if data.name:
#         tenant.name = data.name

#     if data.slug:
#         slug = slugify(data.slug)

#         # 🔥 FIX duplicate slug
#         result = await db.execute(
#             select(Tenant).where(
#                 Tenant.slug == slug,
#                 Tenant.id != tenant_id
#             )
#         )
#         if result.scalar_one_or_none():
#             raise HTTPException(400, "Slug already exists")

#         tenant.slug = slug

#     await db.commit()
#     await db.refresh(tenant)

#     return tenant


# from sqlalchemy import or_, select
# from fastapi import APIRouter, Depends, HTTPException, Query
# from app.accounts.deps import access_three
# from app.accounts.enum import UserRole
# from app.db.config import SessionDep
# from app.accounts.admin.model import Admin
# from app.accounts.tenant.model import Tenant
# from app.accounts.tenant.schemas import TenantOut

# router = APIRouter(prefix="/admin", tags=["Admin"])


# @router.get("/tenants", response_model=list[TenantOut])
# async def get_tenants(
#     db: SessionDep,
#     current=Depends(access_three),
#     skip: int = 0,
#     limit: int = 10,
#     search: str | None = None,
#     partner_id: int | None = Query(None)  # ✅ optional param
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     query = select(Tenant).join(Admin, Tenant.admin_id == Admin.id)

#     # 🔐 ADMIN → only own tenants
#     if role == UserRole.ADMIN:
#         query = query.where(Tenant.admin_id == user.id)

#     # 🔐 PARTNER → all tenants under partner
#     elif role == UserRole.PARTNER:
#         query = query.where(Admin.partner_id == user.id)

#     # 🔐 SUPER ADMIN → MUST PASS partner_id
#     elif role == UserRole.SUPER_ADMIN:
#         if partner_id is None:
#             raise HTTPException(
#                 status_code=400,
#                 detail="partner_id is required for super admin"
#             )

#         # ✅ optional validation (recommended)
#         partner = await db.get(Partner, partner_id)
#         if not partner:
#             raise HTTPException(404, "Invalid partner_id")

#         query = query.where(Admin.partner_id == partner_id)

#     # 🔍 SEARCH FILTER
#     if search:
#         query = query.where(
#             or_(
#                 Tenant.name.ilike(f"%{search}%"),
#                 Tenant.slug.ilike(f"%{search}%")
#             )
#         )

#     result = await db.execute(query.offset(skip).limit(limit))
#     return result.scalars().all()



# @router.get("/tenant/{tenant_id}", response_model=TenantOut)
# async def get_tenant_by_id(
#     tenant_id: int,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     query = (
#         select(Tenant)
#         .join(Admin, Tenant.admin_id == Admin.id)
#         .where(Tenant.id == tenant_id)
#     )

#     if role == UserRole.ADMIN:
#         query = query.where(Tenant.admin_id == user.id)

#     elif role == UserRole.PARTNER:
#         query = query.where(Admin.partner_id == user.id)

#     elif role == UserRole.SUPER_ADMIN:
#         raise HTTPException(400, "Restricted access")

#     result = await db.execute(query)
#     tenant = result.scalar_one_or_none()

#     if not tenant:
#         raise HTTPException(404, "Tenant not found or not allowed")

#     return tenant



# @router.post("/staff", response_model=StaffOut)
# async def create_staff(
#     data: StaffCreate,
#     db: SessionDep,
#     current=Depends(require_admin)
# ):
#     tenant = await get_tenant_if_accessible(
#         tenant_id=data.tenant_id,
#         db=db,
#         current=current
#     )

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




# @router.get("/tenants/{tenant_id}/staff", response_model=list[StaffOut])
# async def get_all_staff(
#     tenant_id: int,
#     db: SessionDep,
#     current=Depends(access_three),
#     skip: int = 0,
#     limit: int = 10,
#     search: str | None = None,
#     is_active: bool | None = None
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     query = (
#         select(Staff)
#         .join(Tenant, Staff.tenant_id == Tenant.id)
#         .join(Admin, Tenant.admin_id == Admin.id)
#         .where(Tenant.id == tenant_id)
#     )

#     if role == UserRole.ADMIN:
#         query = query.where(Tenant.admin_id == user.id)

#     elif role == UserRole.PARTNER:
#         query = query.where(Admin.partner_id == user.id)

#     else:
#         raise HTTPException(403, "Not allowed")

#     if is_active is not None:
#         query = query.where(Staff.is_active == is_active)

#     if search:
#         query = query.where(
#             or_(
#                 Staff.name.ilike(f"%{search}%"),
#                 Staff.email.ilike(f"%{search}%")
#             )
#         )

#     result = await db.execute(query.offset(skip).limit(limit))
#     return result.scalars().all()


# @router.get("/tenants/{tenant_id}/staff/search", response_model=list[StaffOut])
# async def get_staff_by_name(
#     db: SessionDep,
#     tenant_id: int,
#     name: str = Query(..., min_length=1),
#     current=Depends(access_three)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     search_name = name.strip()

#     # 🔐 BASE QUERY (JOIN FULL CHAIN)
#     query = (
#         select(Staff)
#         .join(Tenant, Staff.tenant_id == Tenant.id)
#         .join(Admin, Tenant.admin_id == Admin.id)
#         .where(
#             Tenant.id == tenant_id,
#             Staff.name.ilike(f"%{search_name}%")
#         )
#     )

#     # 🔐 ADMIN → only own tenant
#     if role == UserRole.ADMIN:
#         query = query.where(Tenant.admin_id == user.id)

#     # 🔐 PARTNER → only their admins' tenants
#     elif role == UserRole.PARTNER:
#         query = query.where(Admin.partner_id == user.id)

#     # 🔐 BLOCK SUPER ADMIN (or force filter)
#     else:
#         raise HTTPException(403, "Not allowed")

#     result = await db.execute(query)
#     return result.scalars().all()

# @router.put("/tenants/{tenant_id}/staff/{staff_id}", response_model=StaffOut)
# async def update_staff(
#     tenant_id: int,
#     staff_id: int,
#     data: StaffUpdate,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     admin = current["user"]

#     result = await db.execute(
#         select(Staff)
#         .join(Tenant, Staff.tenant_id == Tenant.id)
#         .where(
#             Staff.id == staff_id,
#             Staff.tenant_id == tenant_id,
#             Tenant.admin_id == admin.id
#         )
#     )

#     staff = result.scalar_one_or_none()

#     if not staff:
#         raise HTTPException(404, "Staff not found or not allowed")

#     if data.name:
#         staff.name = data.name

#     if data.email:
#         email = data.email.lower()

#         result = await db.execute(
#             select(Staff.id).where(
#                 Staff.email == email,
#                 Staff.id != staff_id
#             )
#         )
#         if result.scalar_one_or_none():
#             raise HTTPException(400, "Email already exists")

#         staff.email = email

#     if data.password:
#         staff.password_hash = pwd_context.hash(data.password)

#     if data.is_active is not None:
#         staff.is_active = data.is_active

#     await db.commit()
#     await db.refresh(staff)

#     return staff




# @router.delete("/tenants/{tenant_id}/staff/{staff_id}")
# async def delete_staff(
#     tenant_id: int,
#     staff_id: int,
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     # 🔐 FULL SECURE QUERY
#     query = (
#         select(Staff)
#         .join(Tenant, Staff.tenant_id == Tenant.id)
#         .join(Admin, Tenant.admin_id == Admin.id)
#         .where(
#             Staff.id == staff_id,
#             Staff.tenant_id == tenant_id
#         )
#     )

#     # 🔐 ADMIN → only own tenant staff
#     if role == UserRole.ADMIN:
#         query = query.where(Tenant.admin_id == user.id)

#     # 🔐 PARTNER → only their admins' tenant staff
#     elif role == UserRole.PARTNER:
#         query = query.where(Admin.partner_id == user.id)

#     # 🔐 BLOCK SUPER ADMIN (or force scoped access)
#     else:
#         raise HTTPException(403, "Not allowed")

#     result = await db.execute(query)
#     staff = result.scalar_one_or_none()

#     if not staff:
#         raise HTTPException(404, "Staff not found or not allowed")

#     await db.delete(staff)
#     await db.commit()

#     return {"message": "Staff deleted successfully"}