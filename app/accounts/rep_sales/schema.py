from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    this_week_orders: int
    this_week_revenue: float
    avg_daily_orders: float