"""
app/accounts/crm/notes/router.py

FastAPI router for Customer Notes.
"""

from typing import List
from fastapi import APIRouter
from app.db.config import SessionDep
from app.accounts.crm.notes.schema import CustomerNoteCreate, CustomerNoteOut
from app.accounts.crm.notes import service

router = APIRouter(
    prefix="/crm/notes",
    tags=["CRM Notes"]
)


@router.post("", response_model=CustomerNoteOut)
async def create_note(payload: CustomerNoteCreate, db: SessionDep):
    return await service.create_note(db, payload)


@router.get("", response_model=List[CustomerNoteOut])
async def list_notes(customer_id: int, db: SessionDep):
    return await service.get_customer_notes(db, customer_id)
