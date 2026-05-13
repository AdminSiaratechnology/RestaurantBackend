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