from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class CategoryCreate(BaseModel):
    name: str
    icon: str | None = None
    branch_id: int


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: str | None = None
    branch_id: int
    created_at: datetime | None

    class Config:
        from_attributes = True