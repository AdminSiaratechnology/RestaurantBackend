# app/reports/schemas.py

from datetime import date
from typing import Optional, List, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field


class ReportScope(BaseModel):
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: str = "All Branches"
    is_all_branches: bool = False
    total_branches: int = 1
    date_from: date
    date_to: date
    scope_name: Optional[str] = None


class PaginationMeta(BaseModel):
    page: int = 1
    page_size: int = 50
    total: int = 0
    total_pages: int = 1


class ChartPoint(BaseModel):
    date: Optional[str] = None
    label: str
    amount: float = 0.0
    quantity: Optional[float] = 0.0


class MultiPeriodCharts(BaseModel):
    seven_days: List[ChartPoint] = Field(default_factory=list, alias="7d")
    month: List[ChartPoint] = Field(default_factory=list)
    today: List[ChartPoint] = Field(default_factory=list)
    custom: Optional[List[ChartPoint]] = None

    class Config:
        populate_by_name = True


class TopRankingItem(BaseModel):
    rank: int
    id: Optional[int] = None
    name: str
    icon: Optional[str] = "🍽️"
    quantity: float = 0.0
    amount: float = 0.0
    percent: float = 0.0


T_Summary = TypeVar("T_Summary", bound=Dict[str, Any])
T_Row = TypeVar("T_Row", bound=Dict[str, Any])


class UnifiedReportResponse(BaseModel, Generic[T_Summary, T_Row]):
    success: bool = True
    report: str
    scope: ReportScope
    summary: T_Summary
    chart: List[ChartPoint] = Field(default_factory=list)
    charts: Optional[Dict[str, List[Dict[str, Any]]]] = None
    top_items: Optional[List[TopRankingItem]] = None
    rows: List[T_Row] = Field(default_factory=list)
    pagination: PaginationMeta
