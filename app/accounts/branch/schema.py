
from datetime import datetime
from typing import Optional
from app.accounts.branch.model import statusEnum
from pydantic import BaseModel


class BranchCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    status: str = "active"

    client_id: int
    brand_id: Optional[int] = None


class BranchOut(BaseModel):
    id: int
    name: str
    client_id: int
    brand_id: Optional[int]

    address: Optional[str]
    city: Optional[str]

    status: str

    created_at: datetime | None

    class Config:
        from_attributes = True


class BranchUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    brand_id: int | None = None
    status: str | None = None


class BranchStatusUpdate(BaseModel):
    status: statusEnum