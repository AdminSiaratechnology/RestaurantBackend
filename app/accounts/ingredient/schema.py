from pydantic import BaseModel
from typing import List


class ItemIngredientCreate(BaseModel):
    item_id: int
    inventory_item_id: int
    godown_id: int
    quantity_required: float


class ItemIngredientUpdate(BaseModel):
    quantity_required: float


class BulkIngredientItem(BaseModel):
    inventory_item_id: int
    godown_id: int
    quantity_required: float


class BulkIngredientCreate(BaseModel):
    item_id: int
    ingredients: list[BulkIngredientItem]


class ItemIngredientResponse(BaseModel):
    id: int
    item_id: int
    inventory_item_id: int
    quantity_required: float

    model_config = {
        "from_attributes": True
    }


class IngredientDetail(BaseModel):
    ingredient_id: int

    inventory_item_id: int
    inventory_name: str

    godown_id: int
    godown_name: str

    unit: str

    quantity_required: float


class ItemRecipeResponse(BaseModel):
    item_id: int
    item_name: str
    ingredients: list[IngredientDetail]


