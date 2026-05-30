from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TableShape(str, Enum):
    rectangular = "rectangular"
    round = "round"
    square = "square"
    oval = "oval"


class TableStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    reserved = "reserved"
    inactive = "inactive"


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