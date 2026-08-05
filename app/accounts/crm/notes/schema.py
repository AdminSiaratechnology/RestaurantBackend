"""
app/accounts/crm/notes/schema.py

Pydantic schemas for Customer Notes.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CustomerNoteCreate(BaseModel):
    customer_id: int
    client_id: int
    note: str
    created_by: Optional[str] = None


class CustomerNoteOut(BaseModel):
    id: int
    customer_id: int
    client_id: int
    note: str
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
