from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VisitHistoryOut(BaseModel):

    id: int
    order_id: Optional[int] = None
    bill_id: Optional[int] = None
    branch_id: int

    visit_date: datetime

    total_amount: float
    discount: float
    tax: float
    # net_amount: float

    payment_method: Optional[str] = None
    table_name: Optional[str] = None
    visit_type: Optional[str] = None

    class Config:
        from_attributes = True


class VisitHistoryStatsOut(BaseModel):

    total_visits: int
    total_spend: float
    average_spend: float
    highest_bill: float
    last_visit: Optional[datetime] = None
