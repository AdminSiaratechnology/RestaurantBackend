
from app.accounts.table.enum import TableShape, TableStatus
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional



# class TableStatus(str, Enum):
#     available = "available"
#     occupied = "occupied"
#     reserved = "reserved"
#     inactive = "inactive"


# ✅ Base Schema
class TableBase(BaseModel):
    branch_id: int

    name: str
    floor: str | None = None

    number_of_seats: int = Field(gt=0)

    shape: TableShape = TableShape.rectangular


class TableCreate(BaseModel):
    client_id: int
    branch_id: int
    name: str
    floor: str
    number_of_seats: int
    shape: TableShape


# # ✅ Create Schema
# class TableCreate(TableBase):
#     pass


# ✅ Update Schema
class TableUpdate(BaseModel):
    name: str | None = None
    floor: str | None = None

    number_of_seats: int | None = Field(default=None, gt=0)

    status: TableStatus | None = None

    is_active: bool | None = None

    shape: TableShape | None = None


# ✅ Response Schema
class TableOut(BaseModel):
    id: int

    client_id: int
    branch_id: int

    name: str
    floor: str | None
    floor_id: str | None = None

    number_of_seats: int

    shape: TableShape

    status: TableStatus

    is_active: bool

    created_at: datetime
    updated_at: datetime

    # ── Layout / Canvas Position Fields ──
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    rotation: Optional[float] = None
    layout_width: Optional[float] = None
    layout_height: Optional[float] = None

    @model_validator(mode='after')
    def set_floor_id(self):
        if self.floor:
            self.floor_id = self.floor.strip().lower().replace(" ", "_")
        else:
            self.floor_id = "unassigned"
        return self

    class Config:
        from_attributes = True

class TableStatusUpdate(BaseModel):
    status: TableStatus


# ── Layout Update Schema (for PATCH /tables/{id}/layout) ─────────────────────
class TableLayoutUpdate(BaseModel):
    """
    Payload for updating a table's visual position on the floor canvas.
    All fields optional — only provided fields are updated.
    This schema has NO effect on order/billing/QR/status logic.
    """
    pos_x: Optional[float] = Field(default=None, ge=0, description="Canvas X position in px")
    pos_y: Optional[float] = Field(default=None, ge=0, description="Canvas Y position in px")
    rotation: Optional[float] = Field(default=None, ge=0, le=360, description="Rotation in degrees")
    layout_width: Optional[float] = Field(default=None, gt=0, description="Canvas width in px")
    layout_height: Optional[float] = Field(default=None, gt=0, description="Canvas height in px")


# ── Floor Update Schema (for PATCH /tables/{id}/floor) ───────────────────────
class TableFloorUpdate(BaseModel):
    """
    Payload for updating a table's floor assignment and optionally its layout position.
    """
    floor: str = Field(..., min_length=1, description="Target floor name")
    pos_x: Optional[float] = Field(default=None, ge=0, description="Canvas X position in px")
    pos_y: Optional[float] = Field(default=None, ge=0, description="Canvas Y position in px")



class TableOrderItemOut(BaseModel):
    item_id: int
    item_name: str
    quantity: int
    price: float
    order_status: str


class TableOrderOut(BaseModel):
    order_id: int
    customer_name: str | None
    status: str
    total_amount: float
    items: list[TableOrderItemOut]


class TableDetailsOut(BaseModel):
    table_id: int
    table_name: str
    status: str
    orders: list[TableOrderOut]



class TableOrderItemOut(BaseModel):
    order_item_id: int
    item_id: int
    item_name: str
    quantity: int
    price: float
    subtotal: float
    order_status: str


class TableDetailsOut(BaseModel):
    table_id: int
    table_name: str
    status: str

    customer_name: str | None
    order_id: int | None
    total_amount: float

    items: list[TableOrderItemOut]