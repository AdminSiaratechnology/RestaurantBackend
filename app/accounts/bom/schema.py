from pydantic import BaseModel
from typing import List


class BOMCreate(BaseModel):
    menu_item_id: int
    inventory_item_id: int
    godown_id: int
    qty_required: float


class BOMUpdate(BaseModel):
    qty_required: float


class BulkBOMItem(BaseModel):
    inventory_item_id: int
    godown_id: int
    qty_required: float


class BulkBOMCreate(BaseModel):
    menu_item_id: int
    ingredients: List[BulkBOMItem]


class BOMResponse(BaseModel):
    id: int
    menu_item_id: int
    inventory_item_id: int
    godown_id: int
    qty_required: float

    model_config = {
        "from_attributes": True
    }


class BOMDetail(BaseModel):
    bom_id: int
    inventory_item_id: int
    inventory_name: str
    unit: str
    godown_id: int
    godown_name: str
    qty_required: float


class ItemRecipeResponse(BaseModel):
    item_id: int
    item_name: str
    ingredients: List[BOMDetail]