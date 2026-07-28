from pydantic import BaseModel
from typing import List, Optional


class CategoryDistributionItem(BaseModel):
    category_id: int
    category_name: str
    category_icon: Optional[str] = None
    item_count: int
    percentage: float





class CategoryDistributionResponse(BaseModel):
    total_items: int
    categories: List[CategoryDistributionItem]




class MenuDashboardResponse(BaseModel):
    total_categories: int
    total_items: int
    active_items: int


class TopSellingItem(BaseModel):
    item_id: int
    item_name: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    category_icon: Optional[str] = None
    quantity_sold: int
    percentage: float


class TopSellingItemsResponse(BaseModel):
    total_quantity_sold: int
    items: List[TopSellingItem]