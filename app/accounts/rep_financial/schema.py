from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_revenue: float
    paid_orders: int



class TaxCollectedResponse(BaseModel):
    total_tax_collected: float