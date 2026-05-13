from pydantic import BaseModel

class OrderStatusUpdate(BaseModel):
    status: str



ALLOWED_STATUS_FLOW = {
    "pending": ["preparing"],
    "preparing": ["ready"],
    "ready": ["served"],
    "served": []
}