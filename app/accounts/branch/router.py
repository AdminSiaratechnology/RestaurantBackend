from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.db.config import SessionDep

from app.accounts.branch.model import Branch, statusEnum
from app.accounts.branch.schema import (
    BranchCreate,
    BranchOut,
    BranchUpdate,
    BranchStatusUpdate,
)

from app.accounts.client.model import Client

from app.accounts.deps import (
    access_one,
    UserRole,
    client_access_dependency,
    get_current_user,
    require_roles,
    get_client_if_accessible,
    get_brand_if_accessible,
)


from app.accounts.crm.loyalty.conversion_rule.service import (
    get_or_create_loyalty_conversion_rule,
)


router = APIRouter(
    prefix="/branch",
    tags=["Branch"],
)

branches_router = APIRouter(
    prefix="/branches",
    tags=["Branches"],
)


# ============================================================
# ROLE ACCESS
# ============================================================

branch_access = require_roles(
    UserRole.SUPER_ADMIN,
    UserRole.PARTNER,
    UserRole.CLIENT,
    UserRole.STAFF,
)


# ============================================================
# CREATE BRANCH
# ============================================================

@router.post(
    "/create_branch",
    response_model=BranchOut,
)
@branches_router.post(
    "/create_branch",
    response_model=BranchOut,
)
@branches_router.post(
    "",
    response_model=BranchOut,
)
async def create_branch(
    data: BranchCreate,
    db: SessionDep,
    current=Depends(get_current_user),
):
    # --------------------------------------------------------
    # Validate client access
    # --------------------------------------------------------

    client = await get_client_if_accessible(
        client_id=data.client_id,
        db=db,
        current=current,
    )

    # --------------------------------------------------------
    # Validate brand
    # --------------------------------------------------------

    if data.brand_id is not None:

        brand = await get_brand_if_accessible(
            brand_id=data.brand_id,
            db=db,
            current=current,
        )

        if brand.client_id != client.id:
            raise HTTPException(
                status_code=400,
                detail="Brand must belong to the same client",
            )

    # --------------------------------------------------------
    # Create branch
    # --------------------------------------------------------

    branch = Branch(
        name=data.name,
        client_id=client.id,
        brand_id=data.brand_id,
        address=data.address,
        city=data.city,
        status=data.status,
        branch_code="TEMP",
    )

    db.add(branch)

    await db.flush()

    # --------------------------------------------------------
    # Generate branch code & Default Loyalty Conversion Rule
    # Example: BR001
    # --------------------------------------------------------

    branch.branch_code = f"BR{branch.id:03d}"

    await db.commit()

    await db.refresh(branch)

    # Automatically create default loyalty conversion rule (10 pts = ₹5) for new branch
    await get_or_create_loyalty_conversion_rule(
        db,
        client_id=branch.client_id,
        branch_id=branch.id,
    )

    return branch


# ============================================================
# HELPER: FETCH BRANCHES WITH FILTERING & RBAC
# ============================================================

async def fetch_branches_with_rbac(
    db: SessionDep,
    current: dict,
    client_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    brand_id: Optional[int] = None,
) -> list[Branch]:
    role = UserRole(current["role"])
    user = current["user"]

    # --------------------------------------------------------
    # 1. BASE QUERY ACCORDING TO ROLE-BASED ACCESS CONTROL
    # --------------------------------------------------------

    # SUPER ADMIN: can access all branches
    if role == UserRole.SUPER_ADMIN:
        query = select(Branch)

    # PARTNER: only branches belonging to clients assigned to that partner
    elif role == UserRole.PARTNER:
        query = (
            select(Branch)
            .join(
                Client,
                Client.id == Branch.client_id,
            )
            .where(
                Client.partner_id == user.id
            )
        )

    # CLIENT: only branches belonging to that client
    elif role == UserRole.CLIENT:
        query = (
            select(Branch)
            .where(
                Branch.client_id == user.id
            )
        )

    # STAFF: only their assigned branch
    elif role == UserRole.STAFF:
        if not user.branch_id:
            return []

        query = (
            select(Branch)
            .where(
                Branch.id == user.branch_id
            )
        )

    # UNKNOWN / UNAUTHORIZED ROLE
    else:
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    # --------------------------------------------------------
    # 2. APPLY OPTIONAL FILTERS (AND LOGIC)
    # --------------------------------------------------------

    if client_id is not None:
        query = query.where(Branch.client_id == client_id)

    if branch_id is not None:
        query = query.where(Branch.id == branch_id)

    if brand_id is not None:
        query = query.where(Branch.brand_id == brand_id)

    # --------------------------------------------------------
    # 3. ORDERING
    # --------------------------------------------------------

    query = query.order_by(Branch.id.desc())

    result = await db.execute(query)
    branches = result.scalars().all()
    return list(branches)


# ============================================================
# GET ALL BRANCHES (Supports /branches/all & /branch/get_all_branch)
# ============================================================

@router.get(
    "/get_all_branch",
    response_model=list[BranchOut],
)
@router.get(
    "/all",
    response_model=list[BranchOut],
)
@branches_router.get(
    "/all",
    response_model=list[BranchOut],
)
@branches_router.get(
    "/get_all_branch",
    response_model=list[BranchOut],
)
async def get_branches(
    client_id: Optional[int] = Query(None, gt=0, description="Filter by client ID"),
    branch_id: Optional[int] = Query(None, gt=0, description="Filter by branch ID"),
    brand_id: Optional[int] = Query(None, gt=0, description="Filter by brand ID"),
    db: SessionDep = None,
    current=Depends(access_one),
):
    return await fetch_branches_with_rbac(
        db=db,
        current=current,
        client_id=client_id,
        branch_id=branch_id,
        brand_id=brand_id,
    )


# ============================================================
# GET SINGLE BRANCH
# ============================================================

@router.get(
    "/get_branch/{branch_id}",
    response_model=BranchOut,
)
@branches_router.get(
    "/get_branch/{branch_id}",
    response_model=BranchOut,
)
@branches_router.get(
    "/{branch_id}",
    response_model=BranchOut,
)
async def get_branch(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one),
):
    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    # --------------------------------------------------------
    # Check access
    # --------------------------------------------------------

    await get_client_if_accessible(
        client_id=branch.client_id,
        db=db,
        current=current,
    )

    return branch


# ============================================================
# UPDATE BRANCH
# ============================================================

@router.put(
    "/update_branch/{branch_id}",
    response_model=BranchOut,
)
@branches_router.put(
    "/update_branch/{branch_id}",
    response_model=BranchOut,
)
@branches_router.put(
    "/{branch_id}",
    response_model=BranchOut,
)
async def update_branch(
    branch_id: int,
    data: BranchUpdate,
    db: SessionDep,
    current=Depends(get_current_user),
):
    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    # --------------------------------------------------------
    # Check client access
    # --------------------------------------------------------

    await get_client_if_accessible(
        client_id=branch.client_id,
        db=db,
        current=current,
    )

    # --------------------------------------------------------
    # Update fields
    # --------------------------------------------------------

    if data.name is not None:
        branch.name = data.name

    if data.address is not None:
        branch.address = data.address

    if data.city is not None:
        branch.city = data.city

    if data.status is not None:
        branch.status = data.status

    # --------------------------------------------------------
    # Update brand
    # --------------------------------------------------------

    if data.brand_id is not None:

        brand = await get_brand_if_accessible(
            brand_id=data.brand_id,
            db=db,
            current=current,
        )

        if brand.client_id != branch.client_id:
            raise HTTPException(
                status_code=400,
                detail="Brand must belong to the same client",
            )

        branch.brand_id = data.brand_id

    await db.commit()

    await db.refresh(branch)

    return branch


# ============================================================
# DELETE BRANCH
# ============================================================

@router.delete("/delete_branch/{branch_id}")
@router.delete("/delet_branch/{branch_id}")
@branches_router.delete("/delete_branch/{branch_id}")
@branches_router.delete("/delet_branch/{branch_id}")
@branches_router.delete("/{branch_id}")
async def delete_branch(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one),
):
    role = UserRole(current["role"])
    user = current["user"]

    # =====================================================
    # GET BRANCH
    # =====================================================

    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    # =====================================================
    # ACCESS CONTROL
    # =====================================================

    # SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # PARTNER
    elif role == UserRole.PARTNER:
        client_result = await db.execute(
            select(Client).where(
                Client.id == branch.client_id
            )
        )

        client = client_result.scalar_one_or_none()

        if not client:
            raise HTTPException(
                status_code=404,
                detail="Client not found",
            )

        if client.partner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this branch",
            )

    # CLIENT
    elif role == UserRole.CLIENT:
        if branch.client_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this branch",
            )

    # STAFF
    elif role == UserRole.STAFF:
        if branch.id != user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your assigned branch",
            )

    else:
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    # =====================================================
    # DELETE
    # =====================================================

    await db.delete(branch)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "Branch cannot be deleted because it is being "
                "used by other records."
            ),
        )

    return {
        "message": "Branch deleted successfully",
        "branch_id": branch_id,
    }


# ============================================================
# CHANGE BRANCH STATUS
# ============================================================

@router.patch(
    "/change_status/{branch_id}",
    response_model=BranchOut,
)
@branches_router.patch(
    "/change_status/{branch_id}",
    response_model=BranchOut,
)
@branches_router.patch(
    "/{branch_id}/status",
    response_model=BranchOut,
)
async def change_branch_status(
    branch_id: int,
    data: BranchStatusUpdate,
    db: SessionDep,
    current=Depends(access_one),
):
    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    role = UserRole(current["role"])
    user = current["user"]

    # --------------------------------------------------------
    # SUPER ADMIN
    # --------------------------------------------------------

    if role == UserRole.SUPER_ADMIN:
        pass

    # --------------------------------------------------------
    # PARTNER
    # --------------------------------------------------------

    elif role == UserRole.PARTNER:

        client_result = await db.execute(
            select(Client).where(
                Client.id == branch.client_id
            )
        )

        client = client_result.scalar_one_or_none()

        if not client:
            raise HTTPException(
                status_code=404,
                detail="Client not found",
            )

        if client.partner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not your branch",
            )

    # --------------------------------------------------------
    # CLIENT
    # --------------------------------------------------------

    elif role == UserRole.CLIENT:

        if branch.client_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not your branch",
            )

    # --------------------------------------------------------
    # STAFF
    # --------------------------------------------------------

    elif role == UserRole.STAFF:

        raise HTTPException(
            status_code=403,
            detail="Staff cannot change branch status",
        )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    else:

        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    # --------------------------------------------------------
    # Update status
    # --------------------------------------------------------

    branch.status = data.status

    await db.commit()

    await db.refresh(branch)

    return branch