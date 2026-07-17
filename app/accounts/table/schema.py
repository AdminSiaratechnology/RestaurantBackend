
from app.accounts.table.enum import TableShape, TableStatus
from pydantic import BaseModel, Field
from datetime import datetime



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

    number_of_seats: int

    shape: TableShape

    status: TableStatus

    is_active: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TableStatusUpdate(BaseModel):
    status: TableStatus



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