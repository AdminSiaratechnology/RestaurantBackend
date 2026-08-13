"""
app/accounts/crm/customer_history/schema.py
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ==========================================================
# VISIT HISTORY RESPONSE
# ==========================================================

class VisitHistoryOut(BaseModel):

    id: int

    order_id: Optional[int] = None

    bill_id: Optional[int] = None

    branch_id: int

    visit_date: datetime

    total_amount: float

    discount: float

    tax: float

    # Historical current-spend snapshot
    current_spend: float

    payment_method: Optional[str] = None

    table_name: Optional[str] = None

    visit_type: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )


# ==========================================================
# CUSTOMER VISIT STATS
# ==========================================================

class VisitHistoryStatsOut(BaseModel):

    total_visits: int

    total_spend: float

    current_spend: float

    redeem_count: int

    average_spend: float

    highest_bill: float

    last_visit: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )