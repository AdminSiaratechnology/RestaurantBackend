from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.branch.model import Branch
from app.accounts.branch.schema import BranchCreate, BranchOut, BranchUpdate
from app.accounts.brand.model import Brand
from app.accounts.client.model import Client
from app.accounts.deps import access_three, UserRole, client_access_dependency, get_current_user

from app.accounts.deps import (
    require_roles,
    UserRole,
    get_client_if_accessible,
    get_brand_if_accessible
)

router = APIRouter(prefix="/branch", tags=["Branch"])

branch_access = require_roles(
    UserRole.SUPER_ADMIN,
    UserRole.PARTNER,
    UserRole.CLIENT
)



# @router.post("/create_branch", response_model=BranchOut)
# async def create_branch(
#     data: BranchCreate,
#     db: SessionDep,
#     current=Depends(get_current_user)
# ):
#     role = current["role"]
#     user = current["user"]

#     client = await get_client_if_accessible(
#         client_id=data.client_id,
#         db=db,
#         current=current
#     )

#     if data.brand_id:
#         brand = await get_brand_if_accessible(
#             brand_id=data.brand_id,
#             db=db,
#             current=current
#         )

#         if brand.client_id != client.id:
#             raise HTTPException(400, "Brand must belong to same client")

#     branch = Branch(
#         name=data.name,
#         client_id=client.id,
#         brand_id=data.brand_id,
#         address=data.address,
#         city=data.city
#     )

#     db.add(branch)
#     await db.commit()
#     await db.refresh(branch)

#     return branch



@router.post("/create_branch", response_model=BranchOut)
async def create_branch(
    data: BranchCreate,
    db: SessionDep,
    current=Depends(get_current_user)
):
    client = await get_client_if_accessible(
        client_id=data.client_id,
        db=db,
        current=current
    )

    if data.brand_id:
        brand = await get_brand_if_accessible(
            brand_id=data.brand_id,
            db=db,
            current=current
        )

        if brand.client_id != client.id:
            raise HTTPException(400, "Brand must belong to same client")

    branch = Branch(
        name=data.name,
        client_id=client.id,
        brand_id=data.brand_id,
        address=data.address,
        city=data.city
    )

    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    return branch


# @router.get("/get_all_branch", response_model=list[BranchOut])
# async def get_branches(
#     db: SessionDep,
#     current=Depends(access_three)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     if role == UserRole.SUPER_ADMIN:
#         query = select(Branch)

#     elif role == UserRole.PARTNER:
#         query = (
#             select(Branch)
#             .join(Client)
#             .where(Client.partner_id == user.id)
#         )

#     elif role == UserRole.CLIENT:
#         query = (
#             select(Branch)
#             .join(Client)
#             .where(Client.admin_id == user.id)
#         )

#     result = await db.execute(query)
#     return result.scalars().all()

@router.get("/get_all_branch", response_model=list[BranchOut])
async def get_branches(
    db: SessionDep,
    current=Depends(get_current_user)
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.SUPER_ADMIN:
        query = select(Branch)

    elif role == UserRole.PARTNER:
        query = (
            select(Branch)
            .join(Client)
            .where(Client.partner_id == user.id)
        )

    elif role == UserRole.CLIENT:
        query = (
            select(Branch)
            .where(Branch.client_id == user.id)
        )

    else:
        raise HTTPException(403, "Not allowed")

    result = await db.execute(query)
    return result.scalars().all()




# @router.get("/{branch_id}", response_model=BranchOut)
# async def get_branch(
#     branch_id: int,
#     db: SessionDep,
#     current=Depends(branch_access)
# ):
#     role = UserRole(current["role"])
#     user = current["user"]

#     result = await db.execute(
#         select(Branch).where(Branch.id == branch_id)
#     )
#     branch = result.scalar_one_or_none()

#     if not branch:
#         raise HTTPException(404, "Branch not found")

#     await get_client_if_accessible(
#         db, branch.client_id, role, user
#     )

#     return branch




@router.put("/update_branch/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: int,
    data: BranchUpdate,
    db: SessionDep,
    current=Depends(get_current_user)
):
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(404, "Branch not found")

    await get_client_if_accessible(
        client_id=branch.client_id,
        db=db,
        current=current
    )

    if data.name is not None:
        branch.name = data.name

    if data.address is not None:
        branch.address = data.address

    if data.city is not None:
        branch.city = data.city

    if data.brand_id is not None:

        brand = await get_brand_if_accessible(
            brand_id=data.brand_id,
            db=db,
            current=current
        )

        if brand.client_id != branch.client_id:
            raise HTTPException(400, "Brand mismatch")

        branch.brand_id = data.brand_id

    await db.commit()
    await db.refresh(branch)

    return branch



@router.delete("/delet_branch/{branch_id}")
async def delete_branch(
    branch_id: int,
    db: SessionDep,
    current=Depends(client_access_dependency)
):
    role = UserRole(current["role"])
    user = current["user"]

    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(404, "Branch not found")

    await get_client_if_accessible(
        client_id=branch.client_id,
        db=db,
        current=current
    )

    await db.delete(branch)
    await db.commit()

    return {"message": "Branch deleted"}