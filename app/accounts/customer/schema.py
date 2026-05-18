from datetime import datetime

from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None

    branch_id: int 
    address: str | None = None


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None

    client_id: int
    branch_id: int | None
    branch_name: str | None
    address: str | None

    created_at: datetime | None

    class Config:
        from_attributes = True


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    address: str | None = None
    branch_id: int | None = None