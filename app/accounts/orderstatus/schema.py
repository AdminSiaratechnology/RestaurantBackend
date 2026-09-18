from pydantic import BaseModel

class OrderStatusUpdate(BaseModel):
    status: str



ALLOWED_STATUS_FLOW = {
    "pending": ["accepted", "preparing", "rejected", "cancelled"],
    "accepted": ["preparing", "rejected", "cancelled"],
    "preparing": ["ready", "cancelled"],
    "ready": ["served"],
    "served": [],
    "rejected": [],
    "cancelled": [],
}