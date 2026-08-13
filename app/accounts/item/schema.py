from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field
from app.accounts.item.enum import FoodType


class PricingOut(BaseModel):
    id: int
    branch_id: int
    price: float
    is_active: bool

    model_config = {
        "from_attributes": True
    }


class ItemCreate(BaseModel):
    name: str
    client_id: Optional[int] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    pricing_is_active: Optional[bool] = None
    is_active: bool = True
    food_type: Optional[FoodType] = None


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    pricing_is_active: Optional[bool] = None
    is_active: Optional[bool] = None
    food_type: Optional[FoodType] = None


class ItemOut(BaseModel):
    id: int
    name: str
    client_id: int
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    is_active: bool
    food_type: Optional[FoodType] = None

    pricings: list[PricingOut] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }