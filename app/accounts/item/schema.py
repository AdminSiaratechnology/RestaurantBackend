from datetime import datetime

from pydantic import BaseModel, ConfigDict
from typing import Optional

from app.accounts.pricing.schema import PricingOut

class ItemCreate(BaseModel):
    name: str
    client_id: int
    category_id: int
    branch_id: int
    # image: Optional[str] = None
    # Optional — use POST /pricing/set_pricing for full pricing (tax, discount, etc.)
    price: Optional[float] = None

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    # image: Optional [str] = None
    # pricing fields
    price: Optional[float] = None
    pricing_is_active: Optional[bool] = None

class ItemOut(BaseModel):
    id: int
    name: str
    client_id: int
    category_id: int
    branch_id: int
    image: Optional[str] = None
    created_at: datetime
    is_active: bool

    # ✅ relationship field
    pricings: list[PricingOut] = []

    model_config = ConfigDict(from_attributes=True)