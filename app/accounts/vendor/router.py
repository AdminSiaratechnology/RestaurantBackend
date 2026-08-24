from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from app.db.config import SessionDep
from app.accounts.enum import UserRole
from app.accounts.deps import get_current_user

from app.accounts.vendor.schema import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
)

from app.accounts.vendor.service import VendorService


router = APIRouter(
    prefix="/vendors",
    tags=["Vendors"],
)


# ============================================================
# HELPER
# ============================================================

def get_client_id_from_user(
    current_user,
    requested_client_id: Optional[int] = None,
) -> int:

    user = current_user.get("user")
    role = current_user.get("role")

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user not found",
        )

    # 1. Super Admin
    if role == UserRole.SUPER_ADMIN:
        if requested_client_id:
            return requested_client_id
        return getattr(user, "client_id", None) or 1

    # 2. Partner
    if role == UserRole.PARTNER:
        if requested_client_id:
            return requested_client_id
        return getattr(user, "client_id", None) or 1

    # 3. Client (user.id is the client_id in clients table)
    if role == UserRole.CLIENT:
        return user.id

    # 4. Staff (user.client_id)
    if role == UserRole.STAFF:
        client_id = getattr(user, "client_id", None)
        if client_id is not None:
            return client_id

    # Fallback
    client_id = getattr(user, "client_id", None) or getattr(user, "id", None)
    if requested_client_id:
        return requested_client_id
    if client_id is None:
        raise HTTPException(
            status_code=403,
            detail="User is not associated with a client",
        )

    return client_id


# ============================================================
# CREATE
# ============================================================

@router.post(
    "/create",
    response_model=VendorResponse,
    status_code=201,
)
async def create_vendor(
    payload: VendorCreate,
    db: SessionDep,
    client_id: Optional[int] = Query(None),
    current_user=Depends(get_current_user),
):

    effective_client_id = get_client_id_from_user(
        current_user,
        requested_client_id=client_id,
    )

    return await VendorService.create_vendor(
        db=db,
        payload=payload,
        client_id=effective_client_id,
    )


# ============================================================
# GET ALL
# ============================================================

@router.get(
    "/all",
    response_model=list[VendorResponse],
)
async def get_all_vendors(
    db: SessionDep,
    branch_id: Optional[int] = Query(default=None),
    client_id: Optional[int] = Query(default=None),
    brand_id: Optional[int] = Query(default=None),
    current_user=Depends(get_current_user),
):

    effective_client_id = get_client_id_from_user(
        current_user,
        requested_client_id=client_id,
    )

    return await VendorService.get_all_vendors(
        db=db,
        client_id=effective_client_id,
        branch_id=branch_id,
    )


# ============================================================
# SEARCH
# IMPORTANT: BEFORE /{vendor_id}
# ============================================================

@router.get(
    "/search",
    response_model=list[VendorResponse],
)
async def search_vendors(
    q: str = Query(
        ...,
        min_length=1,
        description=(
            "Search vendor name, code, "
            "mobile or email"
        ),
    ),
    branch_id: Optional[int] = Query(default=None),
    client_id: Optional[int] = Query(default=None),
    db: SessionDep = None,
    current_user=Depends(get_current_user),
):

    effective_client_id = get_client_id_from_user(
        current_user,
        requested_client_id=client_id,
    )

    return await VendorService.search_vendors(
        db=db,
        q=q,
        client_id=effective_client_id,
    )


# ============================================================
# GET SINGLE
# ============================================================

@router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
)
async def get_vendor(
    vendor_id: int,
    db: SessionDep,
    client_id: Optional[int] = Query(default=None),
    current_user=Depends(get_current_user),
):

    effective_client_id = get_client_id_from_user(
        current_user,
        requested_client_id=client_id,
    )

    vendor = await VendorService.get_vendor(
        db=db,
        vendor_id=vendor_id,
        client_id=effective_client_id,
    )

    if not vendor:

        raise HTTPException(
            status_code=404,
            detail="Vendor not found",
        )

    return vendor


# ============================================================
# UPDATE
# ============================================================

@router.put(
    "/{vendor_id}",
    response_model=VendorResponse,
)
async def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: SessionDep,
    client_id: Optional[int] = Query(default=None),
    current_user=Depends(get_current_user),
):

    effective_client_id = get_client_id_from_user(
        current_user,
        requested_client_id=client_id,
    )

    vendor = await VendorService.update_vendor(
        db=db,
        vendor_id=vendor_id,
        payload=payload,
        client_id=effective_client_id,
    )

    if not vendor:

        raise HTTPException(
            status_code=404,
            detail="Vendor not found",
        )

    return vendor


# ============================================================
# DELETE
# ============================================================

@router.delete(
    "/{vendor_id}",
)
async def delete_vendor(
    vendor_id: int,
    db: SessionDep,
    client_id: Optional[int] = Query(default=None),
    current_user=Depends(get_current_user),
):

    effective_client_id = get_client_id_from_user(
        current_user,
        requested_client_id=client_id,
    )

    success = await VendorService.delete_vendor(
        db=db,
        vendor_id=vendor_id,
        client_id=effective_client_id,
    )

    if not success:

        raise HTTPException(
            status_code=404,
            detail="Vendor not found",
        )

    return {
        "message": "Vendor deactivated successfully",
    }