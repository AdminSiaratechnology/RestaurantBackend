from pydantic import BaseModel, EmailStr, Field

class PartnerCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=4)
    is_active: bool = True
    partner_id: int | None = None


class PartnerOut(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True



# app/accounts/partner/schema.py

from pydantic import BaseModel


class PartnerDashboardOut(BaseModel):
    total_clients: int

    active_clients: int
    inactive_clients: int

    new_clients_last_7_days: int

    growth_percentage: float

    total_active: int



class PartnerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None