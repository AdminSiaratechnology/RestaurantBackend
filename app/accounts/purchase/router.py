from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounts.deps import (
    require_purchase_access,
    UserRole,
)
from app.accounts.purchase.model import (
    PurchaseEntry,
    PurchaseEntryItem,
)
from app.accounts.purchase.schema import (
    PurchaseCreate,
    PurchaseInvoicePreviewResponse,
    PurchaseResponse,
    PurchaseUpdate,
)
from app.accounts.purchase.service import (
    create_purchase,
    delete_purchase,
    get_next_invoice_preview,
    get_purchase_by_id,
    get_purchase_items_lookup,
    get_purchases,
    update_purchase,
)
from app.db.config import get_db, SessionDep

router = APIRouter(tags=["Purchases"])


# ============================================================
# INVOICE PREVIEW
# ============================================================

@router.get(
    "/purchases/next-invoice",
    response_model=PurchaseInvoicePreviewResponse,
    summary="Preview next purchase invoice number",
)
@router.get(
    "/purchase-entries/next-invoice",
    response_model=PurchaseInvoicePreviewResponse,
    include_in_schema=False,
)
async def preview_next_invoice(
    branch_id: Optional[int] = Query(None, gt=0),
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        branch_id = user.branch_id

    target_branch_id = branch_id or getattr(user, "branch_id", None) or 1

    return await get_next_invoice_preview(db=db, branch_id=target_branch_id)


# ============================================================
# CREATE PURCHASE
# ============================================================

@router.post(
    "/purchases",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new purchase",
)
@router.post(
    "/purchase-entries",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/purchase-entries/details",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_new_purchase(
    payload: PurchaseCreate,
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF and payload.branch_id != user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create purchase for another branch",
        )

    try:
        purchase = await create_purchase(db=db, payload=payload)
        await db.commit()

        # Eagerly load all relationships with selectinload to prevent MissingGreenlet lazy-loading error during Pydantic response serialization
        stmt = (
            select(PurchaseEntry)
            .options(
                selectinload(PurchaseEntry.items).selectinload(PurchaseEntryItem.inventory_item),
                selectinload(PurchaseEntry.items).selectinload(PurchaseEntryItem.godown),
            )
            .where(PurchaseEntry.id == purchase.id)
        )
        result = await db.execute(stmt)
        return result.scalar_one()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create purchase entry: {str(e)}",
        )


# ============================================================
# LIST PURCHASES
# ============================================================

@router.get(
    "/purchases",
    response_model=List[PurchaseResponse],
    summary="List all purchases",
)
@router.get(
    "/purchase-entries/details",
    response_model=List[PurchaseResponse],
    include_in_schema=False,
)
async def list_purchases(
    branch_id: Optional[int] = Query(None, gt=0),
    supplier_id: Optional[int] = Query(None, gt=0),
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        branch_id = user.branch_id

    return await get_purchases(
        db=db,
        branch_id=branch_id,
        supplier_id=supplier_id,
        skip=skip,
        limit=limit,
    )


# ============================================================
# GET ITEMS FOR PURCHASE SELECTION
# (Must be declared before parameterized path /purchases/{purchase_id})
# ============================================================

@router.get(
    "/purchases/items",
    summary="Get items for purchase by godown and branch",
)
@router.get(
    "/purchase-entries/items",
    include_in_schema=False,
)
async def list_items_for_purchase(
    branch_id: Optional[int] = Query(None, gt=0),
    godown_id: Optional[int] = Query(None, gt=0),
    search: Optional[str] = Query(None),
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        branch_id = user.branch_id

    target_branch_id = branch_id or getattr(user, "branch_id", None) or 1

    return await get_purchase_items_lookup(
        db=db,
        branch_id=target_branch_id,
        godown_id=godown_id,
        search=search,
    )


# ============================================================
# GET PURCHASE BY ID
# ============================================================

@router.get(
    "/purchases/{purchase_id}",
    response_model=PurchaseResponse,
    summary="Get single purchase details by ID",
)
@router.get(
    "/purchase-entries/details/{purchase_id}",
    response_model=PurchaseResponse,
    include_in_schema=False,
)
async def get_purchase(
    purchase_id: int,
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    entry = await get_purchase_by_id(db=db, purchase_id=purchase_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase entry not found",
        )

    role = current["role"]
    user = current["user"]
    if role == UserRole.STAFF and entry.branch_id != user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access purchase of another branch",
        )

    return entry


# ============================================================
# UPDATE PURCHASE
# ============================================================

@router.put(
    "/purchases/{purchase_id}",
    response_model=PurchaseResponse,
    summary="Update purchase entry details",
)
async def update_purchase_entry(
    purchase_id: int,
    payload: PurchaseUpdate,
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    entry = await get_purchase_by_id(db=db, purchase_id=purchase_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase entry not found",
        )

    role = current["role"]
    user = current["user"]
    if role == UserRole.STAFF and entry.branch_id != user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify purchase of another branch",
        )

    try:
        updated = await update_purchase(db=db, purchase_id=purchase_id, payload=payload)
        await db.commit()

        stmt = (
            select(PurchaseEntry)
            .options(
                selectinload(PurchaseEntry.items).selectinload(PurchaseEntryItem.inventory_item),
                selectinload(PurchaseEntry.items).selectinload(PurchaseEntryItem.godown),
            )
            .where(PurchaseEntry.id == updated.id)
        )
        result = await db.execute(stmt)
        return result.scalar_one()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update purchase: {str(e)}",
        )


# ============================================================
# DELETE PURCHASE
# ============================================================

@router.delete(
    "/purchases/{purchase_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete purchase entry",
)
async def remove_purchase(
    purchase_id: int,
    client_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_purchase_access),
):
    entry = await get_purchase_by_id(db=db, purchase_id=purchase_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase entry not found",
        )

    role = current["role"]
    user = current["user"]
    if role == UserRole.STAFF and entry.branch_id != user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete purchase of another branch",
        )

    try:
        await delete_purchase(db=db, purchase_id=purchase_id)
        await db.commit()
        return {"message": "Purchase entry deleted successfully"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete purchase: {str(e)}",
        )

