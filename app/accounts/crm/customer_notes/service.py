from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.customer.model import Customer

from .constants import CustomerNoteType
from .model import CustomerNote
from .schema import (
    CustomerNoteCreate,
    CustomerNoteUpdate,
)


# ============================================================
# CUSTOMER ACCESS
# ============================================================

async def get_customer_for_branch(
    db: AsyncSession,
    *,
    customer_id: int,
    client_id: int,
    branch_id: int,
) -> Customer:

    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client context is missing",
        )

    if branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch context is missing",
        )

    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.client_id == client_id,
            Customer.branch_id == branch_id,
        )
    )

    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return customer


# ============================================================
# NOTE ACCESS
# ============================================================

async def get_note_for_branch(
    db: AsyncSession,
    *,
    note_id: int,
    client_id: int,
    branch_id: int,
) -> CustomerNote:

    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client context is missing",
        )

    if branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch context is missing",
        )

    result = await db.execute(
        select(CustomerNote).where(
            CustomerNote.id == note_id,
            CustomerNote.client_id == client_id,
            CustomerNote.branch_id == branch_id,
        )
    )

    note = result.scalar_one_or_none()

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer note not found",
        )

    return note


# ============================================================
# CREATE NOTE
# ============================================================

async def create_customer_note(
    db: AsyncSession,
    *,
    customer_id: int,
    client_id: int,
    branch_id: int,
    data: CustomerNoteCreate,
    created_by: Optional[int],
) -> CustomerNote:

    await get_customer_for_branch(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    note = CustomerNote(
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
        note=data.note.strip(),
        note_type=data.note_type.value,
        reminder_date=data.reminder_date,
        is_pinned=data.is_pinned,
        created_by=created_by,
        updated_by=created_by,
    )

    db.add(note)

    await db.commit()

    await db.refresh(note)

    return note


# ============================================================
# LIST NOTES
# ============================================================

async def list_customer_notes(
    db: AsyncSession,
    *,
    customer_id: int,
    client_id: int,
    branch_id: int,
    page: int = 1,
    page_size: int = 20,
    note_type: Optional[CustomerNoteType] = None,
    pinned_only: bool = False,
    has_reminder: Optional[bool] = None,
) -> tuple[list[CustomerNote], int]:

    await get_customer_for_branch(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    filters = [
        CustomerNote.customer_id == customer_id,
        CustomerNote.client_id == client_id,
        CustomerNote.branch_id == branch_id,
    ]

    if note_type is not None:
        filters.append(
            CustomerNote.note_type == note_type.value
        )

    if pinned_only:
        filters.append(
            CustomerNote.is_pinned.is_(True)
        )

    if has_reminder is True:
        filters.append(
            CustomerNote.reminder_date.is_not(None)
        )

    elif has_reminder is False:
        filters.append(
            CustomerNote.reminder_date.is_(None)
        )

    # ========================================================
    # COUNT
    # ========================================================

    count_stmt = (
        select(func.count(CustomerNote.id))
        .where(*filters)
    )

    count_result = await db.execute(count_stmt)

    total = count_result.scalar_one() or 0

    # ========================================================
    # PAGINATION
    # ========================================================

    offset = (page - 1) * page_size

    # ========================================================
    # FETCH
    # ========================================================

    stmt = (
        select(CustomerNote)
        .where(*filters)
        .order_by(
            CustomerNote.is_pinned.desc(),
            CustomerNote.created_at.desc(),
            CustomerNote.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(stmt)

    notes = list(result.scalars().all())

    return notes, total


# ============================================================
# GET SINGLE NOTE
# ============================================================

async def get_customer_note(
    db: AsyncSession,
    *,
    note_id: int,
    client_id: int,
    branch_id: int,
) -> CustomerNote:

    return await get_note_for_branch(
        db=db,
        note_id=note_id,
        client_id=client_id,
        branch_id=branch_id,
    )


# ============================================================
# UPDATE NOTE
# ============================================================

async def update_customer_note(
    db: AsyncSession,
    *,
    note_id: int,
    client_id: int,
    branch_id: int,
    data: CustomerNoteUpdate,
    updated_by: Optional[int],
) -> CustomerNote:

    note = await get_note_for_branch(
        db=db,
        note_id=note_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    if "note" in data.model_fields_set:

        if data.note is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Note cannot be null",
            )

        note.note = data.note.strip()

    if "note_type" in data.model_fields_set:

        if data.note_type is None:
            note.note_type = CustomerNoteType.GENERAL.value
        else:
            note.note_type = data.note_type.value

    if "reminder_date" in data.model_fields_set:
        note.reminder_date = data.reminder_date

    if "is_pinned" in data.model_fields_set:

        if data.is_pinned is None:
            note.is_pinned = False
        else:
            note.is_pinned = data.is_pinned

    note.updated_by = updated_by

    await db.commit()

    await db.refresh(note)

    return note


# ============================================================
# DELETE NOTE
# ============================================================

async def delete_customer_note(
    db: AsyncSession,
    *,
    note_id: int,
    client_id: int,
    branch_id: int,
) -> None:

    note = await get_note_for_branch(
        db=db,
        note_id=note_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    await db.delete(note)

    await db.commit()


# ============================================================
# SUMMARY
# ============================================================

async def get_customer_note_summary(
    db: AsyncSession,
    *,
    customer_id: int,
    client_id: int,
    branch_id: int,
) -> dict:

    await get_customer_for_branch(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
    )

    base_filter = [
        CustomerNote.customer_id == customer_id,
        CustomerNote.client_id == client_id,
        CustomerNote.branch_id == branch_id,
    ]

    stmt = (
        select(
            func.count(CustomerNote.id).label(
                "total_notes"
            ),

            func.count(CustomerNote.id)
            .filter(
                CustomerNote.is_pinned.is_(True)
            )
            .label(
                "pinned_notes"
            ),

            func.count(CustomerNote.id)
            .filter(
                CustomerNote.note_type
                == CustomerNoteType.ALLERGY.value
            )
            .label(
                "allergy_notes"
            ),

            func.count(CustomerNote.id)
            .filter(
                CustomerNote.note_type
                == CustomerNoteType.COMPLAINT.value
            )
            .label(
                "complaint_notes"
            ),

            func.count(CustomerNote.id)
            .filter(
                CustomerNote.note_type
                == CustomerNoteType.FEEDBACK.value
            )
            .label(
                "feedback_notes"
            ),

            func.count(CustomerNote.id)
            .filter(
                CustomerNote.note_type
                == CustomerNoteType.PREFERENCE.value
            )
            .label(
                "preference_notes"
            ),

            func.count(CustomerNote.id)
            .filter(
                CustomerNote.note_type
                == CustomerNoteType.FOLLOW_UP.value
            )
            .label(
                "follow_up_notes"
            ),
        )
        .where(*base_filter)
    )

    result = await db.execute(stmt)

    row = result.one()

    return {
        "total_notes": row.total_notes or 0,
        "pinned_notes": row.pinned_notes or 0,
        "allergy_notes": row.allergy_notes or 0,
        "complaint_notes": row.complaint_notes or 0,
        "feedback_notes": row.feedback_notes or 0,
        "preference_notes": row.preference_notes or 0,
        "follow_up_notes": row.follow_up_notes or 0,
    }