from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator
import re
from typing import Optional


class StaffRole(str, Enum):
    manager = "manager"
    waiter = "waiter"
    chef = "chef"


# =========================
# CREATE
# =========================
# class StaffCreate(BaseModel):
#     name: str
#     email: EmailStr
#     password: str
#     role: StaffRole
#     gender: str | None = None
#     phone_number: str | None = None

#     street_address: str | None = None
#     city: str | None = None
#     state: str | None = None
#     pincode: str | None = None


class StaffCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: StaffRole

    gender: str | None = None

    phone_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=15
    )

    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    monthly_salary: float | None = None
    hourly_rate: float | None = None

    aadhaar_number: str | None = None
    pan_number: str | None = None

    bank_account: str | None = None
    ifsc_code: str | None = None
    bank_name: str | None = None

# =========================
# RESPONSE
# =========================
class StaffOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: StaffRole
    client_id: int
    branch_id: int
    gender: str | None
    phone_number: str | None
    is_active: bool
    created_at: datetime | None

    street_address: str | None
    city: str | None
    state: str | None
    pincode: str | None

    monthly_salary: float | None = None
    hourly_rate: float | None = None

    aadhaar_number: str | None = None
    pan_number: str | None = None

    bank_account: str | None = None
    ifsc_code: str | None = None
    bank_name: str | None = None

    class Config:
        from_attributes = True


# =========================
# UPDATE (FIXED - branch_id removed)
# =========================
class StaffUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    role: StaffRole | None = None

    gender: str | None = None

    phone_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=15
    )

    is_active: bool | None = None

    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

class StaffSalaryBankUpdate(BaseModel):

    monthly_salary: Optional[float] = None
    hourly_rate: Optional[float] = None

    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None

    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None

