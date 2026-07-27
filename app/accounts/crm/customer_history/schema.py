from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ==========================================================
# Create Visit
# ==========================================================

class CustomerVisitCreate(BaseModel):

    customer_id: int

    order_id: Optional[int] = None

    bill_id: Optional[int] = None

    visit_type: str = "Dine In"

    visit_channel: str = "POS"

    payment_method: Optional[str] = None

    table_name: Optional[str] = None

    served_by: Optional[str] = None

    total_amount: int = 0

    discount: int = 0

    tax: int = 0

    notes: Optional[str] = None


# ==========================================================
# Update Visit
# ==========================================================

class CustomerVisitUpdate(BaseModel):

    payment_method: Optional[str] = None

    table_name: Optional[str] = None

    served_by: Optional[str] = None

    notes: Optional[str] = None

    visit_status: Optional[str] = None


# ==========================================================
# Visit Response
# ==========================================================

class CustomerVisitOut(BaseModel):

    id: int

    customer_id: int

    order_id: Optional[int]

    bill_id: Optional[int]

    client_id: int

    branch_id: int

    visit_type: str

    visit_channel: str

    visit_status: str

    visit_date: datetime

    total_amount: int

    discount: int

    tax: int

    payment_method: Optional[str]

    table_name: Optional[str]

    served_by: Optional[str]

    notes: Optional[str]

    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================================
# Timeline Item
# ==========================================================

class CustomerTimelineItem(BaseModel):

    id: int

    visit_date: datetime

    visit_type: str

    total_amount: int

    payment_method: Optional[str]

    served_by: Optional[str]

    table_name: Optional[str]

    visit_status: str

    class Config:
        from_attributes = True


# ==========================================================
# Customer Analytics
# ==========================================================

class CustomerVisitAnalytics(BaseModel):

    total_visits: int

    total_orders: int

    total_spend: int

    average_order_value: int

    highest_bill: int

    lowest_bill: int

    first_visit: Optional[datetime]

    last_visit: Optional[datetime]


# ==========================================================
# Dashboard
# ==========================================================

class VisitDashboard(BaseModel):

    today_visits: int

    today_sales: int

    repeat_customers: int

    first_time_customers: int

    vip_visits: int


# ==========================================================
# Recent Visit
# ==========================================================

class RecentVisit(BaseModel):

    customer_name: str

    phone: str

    visit_date: datetime

    total_amount: int

    visit_type: str

    payment_method: Optional[str]