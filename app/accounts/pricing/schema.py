from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class PricingBase(BaseModel):
    item_id: int
    price: float = Field(gt=0)
    is_active: bool = True


class PricingCreate(PricingBase):
    client_id: int


class PricingUpdate(BaseModel):
    price: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


# class PricingOut(BaseModel):
#     id: int
#     client_id: int
#     item_id: int
#     price: float
#     is_active: bool
#     created_at: datetime
#     updated_at: datetime

#     class Config:
#         from_attributes = True

class PricingOut(BaseModel):
    id: int
    price: float
    branch_id: int | None
    item_id: int
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)