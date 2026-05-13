# from fastapi import APIRouter, Depends, HTTPException, Path
# from sqlalchemy import select
# from typing import List
# from app.accounts.admin.model import Admin
# from app.db.config import SessionDep
# from app.accounts.tenant.model import Tenant
# from app.accounts.tenant.schemas import TenantOut, TenantUpdate
# from app.accounts.deps import get_current_user
# from app.accounts.tenant.schemas import TenantCreate
# from app.accounts.deps import require_roles, UserRole, get_tenant_if_accessible,access_three



# router = APIRouter(
#     prefix="/tenant",
#     tags=["Tenant"]
# )



# tenant_access = require_roles(
#     UserRole.SUPER_ADMIN,
#     UserRole.PARTNER,
#     UserRole.ADMIN
# )



# @router.get("/tenants", response_model=list[TenantOut])
# async def get_tenants(
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     if role == UserRole.SUPER_ADMIN:
#         query = select(Tenant)

#     elif role == UserRole.PARTNER:
#         query = (
#             select(Tenant)
#             .join(Admin)
#             .where(Admin.partner_id == user.id)
#         )

#     elif role == UserRole.ADMIN:
#         query = select(Tenant).where(Tenant.admin_id == user.id)

#     result = await db.execute(query)
#     return result.scalars().all()




# @router.get("/tenants/{tenant_id}/modules")
# async def get_tenant_modules(
#     tenant: Tenant = Depends(get_tenant_if_accessible)
# ):
#     return {
#         "tenant_id": tenant.id,
#         "name": tenant.name,
#         "modules": {
#             "brands": len(tenant.brands),
#             "branches": len(tenant.branches),
#         }
#     }
