"""
app/accounts/crm/tags/schema.py

Pydantic schemas for Customer Tags.
"""

from datetime import datetime
from pydantic import BaseModel


class CustomerTagCreate(BaseModel):
    customer_id: int
    client_id: int
    tag_name: str


class CustomerTagOut(BaseModel):
    id: int
    customer_id: int
    client_id: int
    tag_name: str
    created_at: datetime

    class Config:
        from_attributes = True
