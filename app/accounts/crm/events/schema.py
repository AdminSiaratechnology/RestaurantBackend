"""
app/accounts/crm/events/schema.py

Pydantic v2 event payload models and execution context DTO.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class BillCompletedEvent(BaseModel):
    """
    Event payload published when a bill is generated and committed.
    Matches required CRM event format:
    {
        "event": "bill_completed",
        "bill_id": 125,
        "order_id": 98,
        "customer_id": 9,
        "client_id": 1,
        "branch_id": 1
    }
    """
    model_config = ConfigDict(extra="ignore")

    event: str = Field(default="bill_completed", description="Name of the event")
    bill_id: int = Field(..., description="ID of the completed bill")
    order_id: int = Field(..., description="ID of the associated order")
    customer_id: int = Field(..., description="ID of the customer")
    client_id: int = Field(..., description="Client / Organization tenant ID")
    branch_id: int = Field(..., description="Restaurant branch ID")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Event creation timestamp")


class CRMContextDTO(BaseModel):
    """
    Transient data container passed across handler execution pipeline.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event: BillCompletedEvent
    previous_rank: Optional[str] = None
    new_rank: Optional[str] = None
    rank_upgraded: bool = False
    points_earned: float = 0.0
    wallet_credited: float = 0.0
    coupons_issued: list[str] = Field(default_factory=list)
    campaign_events_triggered: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
