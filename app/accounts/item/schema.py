from datetime import datetime

from app.accounts.item.enum import FoodType
from pydantic import BaseModel, ConfigDict
from typing import Optional

from app.accounts.pricing.schema import PricingOut

class ItemCreate(BaseModel):
    name: str
    client_id: int
    category_id: int
    branch_id: int
    price: float | None = None
    food_type: FoodType = FoodType.veg

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    # image: Optional [str] = None
    # pricing fields
    food_type: FoodType | None = None
    price: Optional[float] = None
    pricing_is_active: Optional[bool] = None

class ItemOut(BaseModel):
    id: int
    name: str
    client_id: int
    category_id: int
    branch_id: int
    image: Optional[str] = None
    food_type: FoodType
    created_at: datetime
    is_active: bool

    pricings: list[PricingOut] = []

    model_config = ConfigDict(from_attributes=True)