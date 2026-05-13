from pydantic import BaseModel, EmailStr, Field


class SuperAdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=4)
    is_active: bool = True


class SuperAdminOut(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True


class SuperAdminUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None


class PartnerCreate(BaseModel):
    name: str
    email: EmailStr 
    password: str = Field(min_length=4) 
    is_active: bool = True


class PartnerOut(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True