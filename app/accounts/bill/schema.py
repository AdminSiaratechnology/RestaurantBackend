# =========================================================
# FILE: app/accounts/bill/schema.py
# =========================================================

# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class BillItemOut(BaseModel):

    item_id: int

    item_name: str

    quantity: int

    price: float

    total: float

    class Config:
        from_attributes = True


class BillOut(BaseModel):

    order_id: int

    invoice_no: str

    order_type: str

    customer_name: Optional[str]

    customer_phone: Optional[str]

    table_id: Optional[int]

    payment_status: str

    payment_method: Optional[str]

    created_at: datetime

    items: List[BillItemOut]

    subtotal: float

    cgst_percent: float

    cgst_amount: float

    sgst_percent: float

    sgst_amount: float

    service_charge_percent: float

    service_charge_amount: float

    tax_total: float

    discount_amount: float

    round_off_amount: float

    grand_total: float

    paid_amount: float

    due_amount: float

    footer_message: str

    class Config:
        from_attributes = True