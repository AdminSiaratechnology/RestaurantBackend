from pydantic import BaseModel
from typing import List


class LowStockItem(BaseModel):
    item_id: int
    item_name: str
    current_stock: float
    reorder_level: float
    unit: str


class CategoryStockValue(BaseModel):
    category_name: str
    stock_value: float


class InventoryDashboardResponse(BaseModel):
    total_items: int
    stock_value: float
    low_stock_items: int
    out_of_stock_items: int
    low_stock_list: List[LowStockItem]
    category_stock_value: List[CategoryStockValue]