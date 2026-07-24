from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==========================================================
# Customer Create
# ==========================================================

class CustomerCreate(BaseModel):

    name: str

    phone: str

    email: Optional[str] = None

    address: Optional[str] = None

    gender: Optional[str] = None

    dob: Optional[date] = None

    anniversary: Optional[date] = None

    profile_photo: Optional[str] = None

    customer_source: Optional[str] = "Walk-In"

    customer_type: Optional[str] = "Regular"

    preferred_language: Optional[str] = "English"

    preferred_contact: Optional[str] = "WhatsApp"

    marketing_opt_in: Optional[bool] = True

    remarks: Optional[str] = None

    branch_id: int


# ==========================================================
# Customer Update
# ==========================================================

class CustomerUpdate(BaseModel):

    name: Optional[str] = None

    phone: Optional[str] = None

    email: Optional[str] = None

    address: Optional[str] = None

    gender: Optional[str] = None

    dob: Optional[date] = None

    anniversary: Optional[date] = None

    profile_photo: Optional[str] = None

    customer_source: Optional[str] = None

    customer_type: Optional[str] = None

    status: Optional[str] = None

    current_rank: Optional[str] = None

    preferred_language: Optional[str] = None

    preferred_contact: Optional[str] = None

    marketing_opt_in: Optional[bool] = None

    remarks: Optional[str] = None

    is_vip: Optional[bool] = None

    branch_id: Optional[int] = None


# ==========================================================
# Customer Out
# ==========================================================

class CustomerOut(BaseModel):

    id: int

    name: str

    phone: str

    email: Optional[str]

    address: Optional[str]

    gender: Optional[str]

    dob: Optional[date]

    anniversary: Optional[date]

    profile_photo: Optional[str]

    customer_source: str

    customer_type: str

    status: str

    current_rank: str

    preferred_language: str

    preferred_contact: str

    marketing_opt_in: bool

    is_vip: bool

    remarks: Optional[str]

    first_visit_at: Optional[datetime]

    last_visit_at: Optional[datetime]

    total_orders: int

    total_visits: int

    total_spend: int

    average_order_value: int

    last_order_amount: int

    last_campaign_at: Optional[datetime]

    birthday_wish_sent: bool

    anniversary_wish_sent: bool

    client_id: int

    branch_id: int

    branch_name: Optional[str]

    created_at: datetime

    updated_at: datetime

    class Config:

        from_attributes = True



    # ==========================================================
# Customer Statistics
# ==========================================================

class CustomerStatistics(BaseModel):

    total_orders: int = 0

    total_visits: int = 0

    total_spent: float = 0

    average_bill: float = 0

    highest_bill: float = 0

    lowest_bill: float = 0

    total_discount: float = 0

    total_tax: float = 0

    first_order: Optional[datetime] = None

    last_order: Optional[datetime] = None

    favorite_payment_method: Optional[str] = None

    favorite_order_type: Optional[str] = None

    favorite_item: Optional[str] = None

    favorite_category: Optional[str] = None


# ==========================================================
# Customer List Item
# ==========================================================

class CustomerListItem(BaseModel):

    id: int

    name: str

    phone: str

    email: Optional[str]

    profile_photo: Optional[str]

    branch_name: Optional[str]

    customer_type: str

    current_rank: str

    status: str

    is_vip: bool

    total_orders: int

    total_visits: int

    total_spend: float

    average_order_value: float

    last_order_amount: float

    last_visit: Optional[datetime]

    class Config:

        from_attributes = True


# ==========================================================
# Customer Dashboard
# ==========================================================

class CustomerDashboard(BaseModel):

    total_customers: int

    active_customers: int

    inactive_customers: int

    blocked_customers: int

    vip_customers: int

    new_customers: int

    repeat_customers: int

    bronze_customers: int

    silver_customers: int

    gold_customers: int

    lifetime_revenue: float

    average_order_value: float

    average_customer_value: float


# ==========================================================
# Customer Profile
# ==========================================================

class CustomerProfile(BaseModel):

    customer: CustomerOut

    statistics: CustomerStatistics

    loyalty: Optional[dict] = None

    wallet: Optional[dict] = None

    recent_orders: list = []

    recent_bills: list = []

    favorite_items: list = []

    coupons: list = []

    activities: list = []


# ==========================================================
# Pagination
# ==========================================================

class PaginationResponse(BaseModel):

    page: int

    page_size: int

    total: int

    total_pages: int


# ==========================================================
# Customer List Response
# ==========================================================

class CustomerListResponse(BaseModel):

    items: list[CustomerListItem]

    pagination: PaginationResponse


# ==========================================================
# Customer Filter
# ==========================================================

class CustomerFilter(BaseModel):

    page: int = Field(default=1, ge=1)

    page_size: int = Field(default=20, ge=1, le=100)

    search: Optional[str] = None

    branch_id: Optional[int] = None

    is_vip: Optional[bool] = None

    status: Optional[str] = None

    customer_type: Optional[str] = None

    current_rank: Optional[str] = None

    customer_source: Optional[str] = None

    preferred_contact: Optional[str] = None

    marketing_opt_in: Optional[bool] = None

    sort_by: str = "created_at"

    sort_order: str = "desc"