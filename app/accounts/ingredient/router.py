from fastapi import APIRouter, Depends

from app.accounts.deps import access_one
from app.db.config import SessionDep

from app.accounts.ingredient.schema import (
    ItemIngredientCreate,
    ItemIngredientResponse,
    ItemIngredientUpdate,
    BulkIngredientCreate,
    ItemRecipeResponse
)

from app.accounts.ingredient.service import (
    create_item_ingredient_service,
    bulk_create_ingredients_service,
    get_recipe_by_item_service,
    update_ingredient_service,
    delete_ingredient_service,
    replace_item_ingredients_service
)

router = APIRouter(
    prefix="/ingredient",
    tags=["Ingredient"]
)


@router.post(
    "/",
    response_model=ItemIngredientResponse
)
async def create_item_ingredient(
    data: ItemIngredientCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    return await create_item_ingredient_service(
        data,
        db
    )


@router.post("/bulk")
async def bulk_create_ingredients(
    data: BulkIngredientCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    return await bulk_create_ingredients_service(
        data,
        db
    )


@router.get(
    "/item/{item_id}",
    response_model=ItemRecipeResponse
)
async def get_recipe_by_item(
    item_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    return await get_recipe_by_item_service(
        item_id,
        db
    )


@router.patch(
    "/{ingredient_id}",
    response_model=ItemIngredientResponse
)
async def update_ingredient(
    ingredient_id: int,
    data: ItemIngredientUpdate,
    db: SessionDep,
    current=Depends(access_one)
):
    return await update_ingredient_service(
        ingredient_id,
        data,
        db
    )


@router.delete("/{ingredient_id}")
async def delete_ingredient(
    ingredient_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    return await delete_ingredient_service(
        ingredient_id,
        db
    )


@router.put("/item/{item_id}/ingredients")
async def replace_item_ingredients(
    item_id: int,
    data: BulkIngredientCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    return await replace_item_ingredients_service(
        item_id,
        data,
        db
    )