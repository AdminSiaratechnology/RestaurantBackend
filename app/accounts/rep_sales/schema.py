from typing import List
from pydantic import BaseModel


# =========================================================
# KPI SUMMARY
# =========================================================

class DashboardSummaryResponse(BaseModel):
    this_week_orders: int
    this_week_revenue: float
    avg_daily_orders: float


# =========================================================
# SALES TREND ITEM
# =========================================================

class SalesTrendItem(BaseModel):
    label: str
    date: str
    orders: int
    revenue: float


# =========================================================
# SALES TREND RESPONSE
# =========================================================

class SalesTrendResponse(BaseModel):
    period: str
    total_orders: int
    total_revenue: float
    data: List[SalesTrendItem]


# =========================================================
# COMPLETE SALES DASHBOARD
# =========================================================

class SalesDashboardResponse(BaseModel):
    summary: DashboardSummaryResponse
    trend: SalesTrendResponse


# =========================================================
# BRANCH SALES SUMMARY
# =========================================================

class BranchSalesSummary(BaseModel):
    branch_id: int
    branch_name: str

    this_week_orders: int
    this_week_revenue: float
    avg_daily_orders: float


class AllBranchesSalesResponse(BaseModel):
    this_week_orders: int
    this_week_revenue: float
    avg_daily_orders: float

    branches: List[BranchSalesSummary]