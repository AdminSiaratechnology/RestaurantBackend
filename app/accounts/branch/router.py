from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.branch.model import Branch, statusEnum
from app.accounts.branch.schema import BranchCreate, BranchOut, BranchUpdate, BranchStatusUpdate
from app.accounts.brand.model import Brand
from app.accounts.client.model import Client
from app.accounts.deps import access_one, UserRole, client_access_dependency, get_current_user

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
    UserRole.CLIENT,
    UserRole.STAFF
)






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
        city=data.city,
        status=data.status,
        branch_code="" 
    )

    db.add(branch)
    await db.flush()
    branch.branch_code = f"BR{branch.id:03d}"
    await db.commit()
    await db.refresh(branch)

    return branch




@router.get("/get_all_branch", response_model=list[BranchOut])
async def get_branches(
    db: SessionDep,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        query = select(Branch)

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = (
            select(Branch)
            .join(Client)
            .where(Client.partner_id == user.id)
        )

    # ✅ CLIENT
    elif role == UserRole.CLIENT:
        query = (
            select(Branch)
            .where(Branch.client_id == user.id)
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:

        # only assigned branch
        query = (
            select(Branch)
            .where(Branch.id == user.branch_id)
        )

    else:
        raise HTTPException(403, "Not allowed")

    result = await db.execute(query)

    return result.scalars().all()









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
    
    if data.status is not None:
        branch.status = data.status

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




@router.patch("/change_status/{branch_id}", response_model=BranchOut)
async def change_branch_status(
    branch_id: int,
    data: BranchStatusUpdate,
    db: SessionDep,
    current=Depends(access_one)
):
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found"
        )

    role = current["role"]
    user = current["user"]

    # SUPER ADMIN → allowed
    if role == UserRole.SUPER_ADMIN:
        pass

    # PARTNER → branch must belong to partner's client
    elif role == UserRole.PARTNER:
        client_result = await db.execute(
            select(Client).where(Client.id == branch.client_id)
        )
        client = client_result.scalar_one()

        if client.partner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not your branch"
            )

    # CLIENT → branch must belong to client
    elif role == UserRole.CLIENT:
        if branch.client_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not your branch"
            )

    # STAFF → not allowed
    else:
        raise HTTPException(
            status_code=403,
            detail="Not allowed"
        )

    branch.status = data.status.value

    await db.commit()
    await db.refresh(branch)

    return branch