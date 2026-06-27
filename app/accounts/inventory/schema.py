

from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Optional

UNIT_MAPPING = {
    "gm": ("gm", 1),
    "kg": ("gm", 1000),

    "ml": ("ml", 1),
    "litre": ("ml", 1000),

    "piece": ("piece", 1),
    "dozen": ("piece", 12),
    "tray": ("piece", 30),
}

VALID_UNITS = list(UNIT_MAPPING.keys())


class InventoryCreate(BaseModel):
    branch_id: int
    godown_id: Optional[int] = None

    name: str

    row_category: Optional[str] = "other"

    unit: str
    display_unit: Optional[str] = None
    conversion_factor: Optional[float] = None

    stock_qty: float
    reorder_level: float
    cost_per_unit: float

    vendor_name: Optional[str] = None
    vendor_phone: Optional[str] = None

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value):
        value = value.lower()

        if value not in VALID_UNITS:
            raise ValueError(
                f"Unit must be one of {VALID_UNITS}"
            )

        return value

class InventoryResponse(BaseModel):
    id: int
    name: str
    godown_id: Optional[int] = None
    row_category: str
    unit: str
    display_unit: str
    conversion_factor: float
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




class GodownCreate(BaseModel):
    branch_id: int
    name: str
    code: Optional[str] = None
    address: Optional[str] = None


class GodownUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None


class GodownOut(BaseModel):
    id: int
    branch_id: int
    name: str
    code: Optional[str]
    address: Optional[str]

    class Config:
        from_attributes = True







class StockUpdate(BaseModel):
    quantity: Optional[float] = None
    unit: Optional[str] = None
    operation: Optional[str] = "set"
    name: Optional[str] = None
    row_category: Optional[str] = None
    stock_qty: Optional[float] = None
    reorder_level: Optional[float] = None
    cost_per_unit: Optional[float] = None
    vendor_name: Optional[str] = None
    vendor_phone: Optional[str] = None
    godown_id: Optional[int] = None
    last_restocked: Optional[datetime] = None

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value):
        if value is None:
            return value

        value = value.lower()

        if value not in VALID_UNITS:
            raise ValueError(
                f"Unit must be one of {VALID_UNITS}"
            )

        return value

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value):
        if value is None:
            return value

        value = value.lower()

        if value not in ["add", "subtract", "set"]:
            raise ValueError(
                "operation must be add, subtract or set"
            )

        return value


