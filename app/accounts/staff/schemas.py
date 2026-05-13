from pydantic import BaseModel, EmailStr
from datetime import datetime


class StaffCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class StaffOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    client_id: int

    is_active: bool
    created_at: datetime | None

    class Config:
        from_attributes = True


class StaffUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None