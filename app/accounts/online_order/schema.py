from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from typing import Optional, List, Any

from .model import (
    OnlinePlatform,
    OnlineOrderStatus,
)


# =========================================================
# REJECT ORDER
# =========================================================

class OnlineOrderReject(BaseModel):

    reason: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    note: Optional[str] = None


# =========================================================
# UPDATE LIST / FILTER
# =========================================================

class OnlineOrderFilter(BaseModel):

    branch_id: Optional[int] = None

    platform: Optional[OnlinePlatform] = None

    status: Optional[OnlineOrderStatus] = None


# =========================================================
# ORDER ITEM RESPONSE
# =========================================================

class OnlineOrderItemOut(BaseModel):

    id: int

    item_id: int

    item_name: Optional[str] = None

    quantity: int

    unit_price: float

    total_price: float

    order_status: str

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# ONLINE ORDER RESPONSE
# =========================================================

class OnlineOrderOut(BaseModel):

    order_id: int

    client_id: int

    branch_id: int

    customer_name: Optional[str]

    customer_phone: Optional[str]

    notes: Optional[str]

    total_amount: float

    order_status: str

    platform: OnlinePlatform

    external_order_id: str

    external_order_number: Optional[str]

    online_status: OnlineOrderStatus

    rejection_reason: Optional[str]

    rejection_note: Optional[str]

    received_at: datetime

    accepted_at: Optional[datetime]

    ready_at: Optional[datetime]

    picked_up_at: Optional[datetime]

    out_for_delivery_at: Optional[datetime]

    delivered_at: Optional[datetime]

    items: List[OnlineOrderItemOut]

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# SUMMARY
# =========================================================

class OnlineOrderSummaryOut(BaseModel):

    pending: int

    accepted: int

    ready_for_pickup: int

    picked_up: int

    out_for_delivery: int

    delivered: int

    rejected: int

    cancelled: int





# =========================================================
# PLATFORM STATUS WEBHOOK
# =========================================================

class PlatformStatusWebhook(BaseModel):

    event_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    external_order_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    status: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    event_type: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    metadata: Optional[dict] = None