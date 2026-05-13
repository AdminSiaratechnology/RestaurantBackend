from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class OrderItemCreate(BaseModel):
    item_id: int
    quantity: int


class OrderCreate(BaseModel):
    client_id: int
    branch_id: int
    table_id: Optional[int] = None

    order_type: str

    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    notes: Optional[str] = None

    items: List[OrderItemCreate]


class OrderItemResponse(BaseModel):
    item_id: int
    quantity: int
    price: float


class OrderResponse(BaseModel):
    id: int

    client_id: int
    branch_id: int
    table_id: Optional[int]

    order_type: str

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
    order_type: str | None = None
    items: list[OrderItemUpdate] | None = None