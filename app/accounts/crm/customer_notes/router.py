from math import ceil
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.deps import get_current_user
from app.accounts.enum import UserRole
from app.db.config import get_db

from app.accounts.customer.model import Customer

from .constants import CustomerNoteType
from .model import CustomerNote
from .schema import (
    CustomerNoteCreate,
    CustomerNoteListResponse,
    CustomerNoteResponse,
    CustomerNoteSummary,
    CustomerNoteUpdate,
)
from .service import (
    create_customer_note,
    delete_customer_note,
    get_customer_note,
    get_customer_note_summary,
    list_customer_notes,
    update_customer_note,
)


router = APIRouter(
    prefix="/crm",
    tags=["CRM - Customer Notes"],
)


# ============================================================
# AUTH CONTEXT
# ============================================================

async def get_auth_context(
    db: AsyncSession,
    current_user,
    customer_id: Optional[int] = None,
    note_id: Optional[int] = None,
):
    """
    Resolve authenticated tenant/client/branch context.

    Important:
    - CLIENT users may not have branch_id directly.
    - For customer-specific endpoints, branch is resolved
      from the customer after validating client ownership.
    - For note-specific endpoints, branch is resolved from
      the note/customer after validating client ownership.
    """

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication context missing",
        )

    user = current_user.get("user")
    role = current_user.get("role")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user missing",
        )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user role missing",
        )

    # --------------------------------------------------------
    # USER ID
    # --------------------------------------------------------

    user_id = getattr(
        user,
        "id",
        None,
    )

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user ID missing",
        )

    # --------------------------------------------------------
    # INITIAL CONTEXT
    # --------------------------------------------------------

    client_id = getattr(
        user,
        "client_id",
        None,
    )

    branch_id = getattr(
        user,
        "branch_id",
        None,
    )

    # ========================================================
    # CLIENT
    # ========================================================

    if role == UserRole.CLIENT:

        # In your current auth architecture JWT user_id
        # represents the client id for client login.
        client_id = user_id

        # Client account may not have a direct branch_id.
        # Resolve it from the requested customer.
        if branch_id is None and customer_id is not None:

            result = await db.execute(
                select(
                    Customer.branch_id
                ).where(
                    Customer.id == customer_id,
                    Customer.client_id == client_id,
                )
            )

            branch_id = result.scalar_one_or_none()

            if branch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found",
                )

        # ----------------------------------------------------
        # NOTE-SPECIFIC REQUEST
        # ----------------------------------------------------

        elif branch_id is None and note_id is not None:

            result = await db.execute(
                select(
                    CustomerNote.branch_id
                ).where(
                    CustomerNote.id == note_id,
                    CustomerNote.client_id == client_id,
                )
            )

            branch_id = result.scalar_one_or_none()

            if branch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer note not found",
                )

    # ========================================================
    # STAFF
    # ========================================================

    elif role == UserRole.STAFF:

        if client_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff is not associated with a client",
            )

        if branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff is not associated with a branch",
            )

    # ========================================================
    # PARTNER / SUPER ADMIN
    # ========================================================

    elif role in (
        UserRole.PARTNER,
        UserRole.SUPER_ADMIN,
    ):

        if client_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client context could not be resolved",
            )

        # ----------------------------------------------------
        # CUSTOMER-SPECIFIC
        # ----------------------------------------------------

        if branch_id is None and customer_id is not None:

            result = await db.execute(
                select(
                    Customer.branch_id
                ).where(
                    Customer.id == customer_id,
                    Customer.client_id == client_id,
                )
            )

            branch_id = result.scalar_one_or_none()

            if branch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found",
                )

        # ----------------------------------------------------
        # NOTE-SPECIFIC
        # ----------------------------------------------------

        elif branch_id is None and note_id is not None:

            result = await db.execute(
                select(
                    CustomerNote.branch_id
                ).where(
                    CustomerNote.id == note_id,
                    CustomerNote.client_id == client_id,
                )
            )

            branch_id = result.scalar_one_or_none()

            if branch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer note not found",
                )

    # ========================================================
    # UNKNOWN ROLE
    # ========================================================

    else:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role is not allowed",
        )

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client context could not be resolved",
        )

    if branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch context could not be resolved",
        )

    return (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    )


# ============================================================
# CREATE NOTE
# ============================================================

@router.post(
    "/customers/{customer_id}/notes",
    response_model=CustomerNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    customer_id: int,
    data: CustomerNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):

    (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    ) = await get_auth_context(
        db=db,
        current_user=current_user,
        customer_id=customer_id,
    )

    return await create_customer_note(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
        data=data,
        created_by=user_id,
    )


# ============================================================
# LIST NOTES
# ============================================================

@router.get(
    "/customers/{customer_id}/notes",
    response_model=CustomerNoteListResponse,
)
async def list_notes(
    customer_id: int,

    page: int = Query(
        1,
        ge=1,
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100,
    ),

    note_type: Optional[CustomerNoteType] = Query(
        None,
    ),

    pinned_only: bool = Query(
        False,
    ),

    has_reminder: Optional[bool] = Query(
        None,
    ),

    db: AsyncSession = Depends(get_db),

    current_user=Depends(get_current_user),
):

    (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    ) = await get_auth_context(
        db=db,
        current_user=current_user,
        customer_id=customer_id,
    )

    notes, total = await list_customer_notes(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        note_type=note_type,
        pinned_only=pinned_only,
        has_reminder=has_reminder,
    )

    total_pages = (
        ceil(total / page_size)
        if total > 0
        else 0
    )

    return CustomerNoteListResponse(
        items=notes,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


# ============================================================
# SUMMARY
# ============================================================

@router.get(
    "/customers/{customer_id}/notes/summary",
    response_model=CustomerNoteSummary,
)
async def get_notes_summary(
    customer_id: int,

    db: AsyncSession = Depends(get_db),

    current_user=Depends(get_current_user),
):

    (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    ) = await get_auth_context(
        db=db,
        current_user=current_user,
        customer_id=customer_id,
    )

    return await get_customer_note_summary(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
    )


# ============================================================
# GET SINGLE NOTE
# ============================================================

@router.get(
    "/customer-notes/{note_id}",
    response_model=CustomerNoteResponse,
)
async def get_note(
    note_id: int,

    db: AsyncSession = Depends(get_db),

    current_user=Depends(get_current_user),
):

    # --------------------------------------------------------
    # Resolve auth context using NOTE ID
    # --------------------------------------------------------

    (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    ) = await get_auth_context(
        db=db,
        current_user=current_user,
        note_id=note_id,
    )

    return await get_customer_note(
        db=db,
        note_id=note_id,
        client_id=client_id,
        branch_id=branch_id,
    )


# ============================================================
# UPDATE NOTE
# ============================================================

@router.patch(
    "/customer-notes/{note_id}",
    response_model=CustomerNoteResponse,
)
async def update_note(
    note_id: int,

    data: CustomerNoteUpdate,

    db: AsyncSession = Depends(get_db),

    current_user=Depends(get_current_user),
):

    # --------------------------------------------------------
    # Resolve branch using note ID
    # --------------------------------------------------------

    (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    ) = await get_auth_context(
        db=db,
        current_user=current_user,
        note_id=note_id,
    )

    return await update_customer_note(
        db=db,
        note_id=note_id,
        client_id=client_id,
        branch_id=branch_id,
        data=data,
        updated_by=user_id,
    )


# ============================================================
# DELETE NOTE
# ============================================================

@router.delete(
    "/customer-notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    note_id: int,

    db: AsyncSession = Depends(get_db),

    current_user=Depends(get_current_user),
):

    # --------------------------------------------------------
    # Resolve branch using note ID
    # --------------------------------------------------------

    (
        user,
        client_id,
        branch_id,
        user_id,
        role,
    ) = await get_auth_context(
        db=db,
        current_user=current_user,
        note_id=note_id,
    )

    await delete_customer_note(
        db=db,
        note_id=note_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    return None