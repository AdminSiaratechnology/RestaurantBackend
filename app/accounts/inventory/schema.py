from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InventoryCreate(BaseModel):
    client_id: int
    branch_id: int
    name: str
    row_category: Optional[str] = "other"
    unit: Optional[str] = "pieces"

    stock_qty: float
    reorder_level: float
    cost_per_unit: float

    vendor_name: Optional[str] = None
    vendor_phone: Optional[str] = None

    last_restocked: Optional[datetime] = None


class InventoryResponse(BaseModel):
    id: int
    name: str
    row_category: str
    unit: str
    stock_qty: float
    reorder_level: float
    cost_per_unit: float
    total_value: float
    status: str
    vendor_name: Optional[str]
    vendor_phone: Optional[str]
    last_restocked: Optional[datetime]

    class Config:
        from_attributes = True