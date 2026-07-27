from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel
from datetime import datetime
from app.accounts.order.enum import OrderType

T = TypeVar('T')

class CursorPaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[int]
    has_more: bool
    total_count: int


class OrderItemCreate(BaseModel):
    item_id: int
    quantity: int



class OrderCreate(BaseModel):
    client_id: int
    branch_id: int
    table_id: Optional[int] = None

    order_type: OrderType

    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    notes: Optional[str] = None

    items: List[OrderItemCreate]



class OrderItemResponse(BaseModel):
    id: int
    item_id: int
    quantity: int
    price: float
    order_status: str

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int

    client_id: int
    branch_id: int
    table_id: Optional[int]
    table_number: Optional[str] = None

    order_type: OrderType

    customer_name: Optional[str]
    customer_phone: Optional[str]

    notes: Optional[str]

    status: str
    total_amount: float

    created_at: datetime

    items: List[OrderItemResponse]

    class Config:
        from_attributes = True


class OrderItemUpdate(BaseModel):
    item_id: int
    quantity: int


class OrderUpdate(BaseModel):
    notes: str | None = None
    order_type: OrderType | None = None
    items: list[OrderItemUpdate] | None = None



class OrderItemStatusUpdate(BaseModel):
    order_status: str


class OrderItemStatusResponse(BaseModel):
    id: int
    order_id: int
    item_id: int
    quantity: int
    order_status: str

    class Config:
        from_attributes = True