from pydantic import BaseModel, EmailStr
from typing import Optional

from app.accounts.client.service import get_staff_all_branches
class ClientCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    partner_id: Optional[int] = None   # only for superadmin
    is_active: Optional[bool] = True 

class ClientUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    is_active: Optional[bool]


class ClientOut(BaseModel):
    id: int
    name: str
    email: str
    partner_id: int
    is_active: bool

    class Config:
        from_attributes = True