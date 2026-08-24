from datetime import date
from typing import List

from pydantic import BaseModel, ConfigDict


class PurchaseReportKPI(BaseModel):
    today_purchase: float = 0.0
    last_7_days_purchase: float = 0.0
    current_month_purchase: float = 0.0
    total_purchase_entries: int = 0


class PurchaseChartPoint(BaseModel):
    date: date
    label: str
    amount: float = 0.0


class TopPurchasingItem(BaseModel):
    rank: int
    inventory_item_id: int
    item_name: str
    total_quantity: float = 0.0
    total_amount: float = 0.0
    percentage_of_total: float = 0.0


class PurchaseReportResponse(BaseModel):
    branch_id: int
    branch_name: str

    kpis: PurchaseReportKPI

    chart: dict

    top_purchasing_items: List[TopPurchasingItem]


class ClientBranchPurchaseReport(BaseModel):
    branch_id: int
    branch_name: str
    report: PurchaseReportResponse


class ClientPurchaseReportResponse(BaseModel):
    client_id: int
    branches: List[ClientBranchPurchaseReport]