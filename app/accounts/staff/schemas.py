from pydantic import BaseModel, EmailStr
from datetime import datetime
from enum import Enum


class StaffRole(str, Enum):
    manager = "manager"
    waitr = "waitr"
    chef = "chef"


class StaffCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

    role: StaffRole
    branch_id: int


class StaffOut(BaseModel):
    id: int

    name: str

    email: EmailStr

    role: StaffRole

    client_id: int

    branch_id: int

    is_active: bool

    created_at: datetime | None

    class Config:
        from_attributes = True


class StaffUpdate(BaseModel):
    name: str | None = None

    email: EmailStr | None = None

    password: str | None = None

    role: StaffRole | None = None

    branch_id: int | None = None

    is_active: bool | None = None