from pydantic import BaseModel


class TopClientOut(BaseModel):
    client_id: int
    name: str
    total_orders: int
    revenue: float
    growth: float | None = 0
 
    class Config:
        from_attributes = True