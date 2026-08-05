"""
app/accounts/crm/notes/service.py

Services for Customer Notes.
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.accounts.crm.notes.model import CustomerNote
from app.accounts.crm.notes.schema import CustomerNoteCreate


async def create_note(db: AsyncSession, payload: CustomerNoteCreate) -> CustomerNote:
    note = CustomerNote(**payload.model_dump())
    db.add(note)
    await db.flush()
    return note


async def get_customer_notes(db: AsyncSession, customer_id: int) -> List[CustomerNote]:
    stmt = select(CustomerNote).where(CustomerNote.customer_id == customer_id).order_by(CustomerNote.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()
