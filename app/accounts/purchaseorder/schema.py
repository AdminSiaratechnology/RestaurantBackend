from datetime import datetime

from pydantic import BaseModel, field_validator
from typing import Optional


class PurchaseOrderItemCreate(BaseModel):
    inventory_item_id: int
    quantity: float
    unit_price: float

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value):
        if value <= 0:
            raise ValueError(
                "quantity must be greater than 0"
            )
        return value

    @field_validator("unit_price")
    @classmethod
    def validate_price(cls, value):
        if value < 0:
            raise ValueError(
                "unit_price cannot be negative"
            )
        return value


class PurchaseOrderCreate(BaseModel):
    branch_id: int
    godown_id: int

    vendor_name: str
    vendor_phone: Optional[str] = None

    notes: Optional[str] = None

    items: list[PurchaseOrderItemCreate]


class PurchaseOrderItemResponse(BaseModel):
    id: int

    inventory_item_id: int

    quantity: float
    received_qty: float

    unit_price: float
    subtotal: float

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: int

    po_number: str

    branch_id: int
    godown_id: int

    vendor_name: str
    vendor_phone: Optional[str]

    status: str

    total_amount: float

    notes: Optional[str]

    created_at: datetime

    items: list[PurchaseOrderItemResponse]

    class Config:
        from_attributes = True


class ReceiveItem(BaseModel):
    purchase_order_item_id: int
    received_qty: float


class ReceiveStockRequest(BaseModel):
    items: list[ReceiveItem] 


class ReceiveItem(BaseModel):
    purchase_order_item_id: int
    received_qty: float

    @field_validator("received_qty")
    @classmethod
    def validate_received_qty(cls, value):
        if value <= 0:
            raise ValueError(
                "received_qty must be greater than 0"
            )
        return value
    

class PurchaseOrderUpdate(BaseModel):
    vendor_name: str
    vendor_phone: Optional[str] = None
    notes: Optional[str] = None

    items: list[PurchaseOrderItemCreate]


class PurchaseOrderUpdate(BaseModel):
    vendor_name: str
    vendor_phone: Optional[str] = None
    notes: Optional[str] = None

    items: list[PurchaseOrderItemCreate]

    @field_validator("items")
    @classmethod
    def validate_items(cls, value):
        if not value:
            raise ValueError(
                "At least one item is required"
            )
        return value