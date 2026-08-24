# app/reports/category/schema.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.reports.schemas import ReportScope, PaginationMeta, ChartPoint, TopRankingItem


class CategoryReportSummary(BaseModel):
    total_categories: int = 0
    total_menu_items: int = 0
    total_items: int = 0
    active_categories: int = 0
    active_items: int = 0
    top_category: str = "None"
    total_category_sales: float = 0.0


class CategoryReportRow(BaseModel):
    sr_no: int
    id: int
    branch_id: int
    branch_name: str
    name: str
    icon: Optional[str] = "🍽️"
    total_items: int = 0
    active_items: int = 0
    sold_quantity: float = 0.0
    sales_amount: float = 0.0
    percentage_of_total: float = 0.0


class CategoryReportResponse(BaseModel):
    success: bool = True
    report: str = "category"
    scope: ReportScope
    summary: CategoryReportSummary
    chart: List[ChartPoint] = []
    charts: Optional[Dict[str, List[Dict[str, Any]]]] = None
    top_items: Optional[List[TopRankingItem]] = None
    rows: List[CategoryReportRow] = []
    pagination: PaginationMeta
