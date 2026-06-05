
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, delete
from passlib.context import CryptContext
from app.accounts.branch.model import Branch
from app.accounts.deps import require_client, get_current_user, UserRole
from app.accounts.ingredient.model import ItemIngredient
from app.accounts.ingredient.schema import (
    ItemIngredientCreate,
    ItemIngredientResponse,
    ItemIngredientUpdate,
    BulkIngredientCreate,
    ItemRecipeResponse
)
from app.accounts.bom.model import MenuItemBOM
from app.db.config import SessionDep
from app.accounts.deps import access_one
from app.accounts.item.model import Item
from app.accounts.inventory.model import InventoryItem, Godown



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
    
    existing = await db.execute(
        select(ItemIngredient).where(
            ItemIngredient.item_id == data.item_id,
            ItemIngredient.inventory_item_id == data.inventory_item_id,
            ItemIngredient.godown_id == data.godown_id
        )
    )

    existing = existing.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ingredient already exists for this item and godown"
        )

    ingredient = ItemIngredient(
        item_id=data.item_id,
        inventory_item_id=data.inventory_item_id,
        godown_id=data.godown_id,
        quantity_required=data.quantity_required
    )

    db.add(ingredient)

    await db.commit()
    await db.refresh(ingredient)

    return ingredient



@router.post("/bulk")
async def bulk_create_ingredients(
    data: BulkIngredientCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    created = []

    for ingredient in data.ingredients:
        row = ItemIngredient(
            item_id=data.item_id,
            inventory_item_id=ingredient.inventory_item_id,
            godown_id=ingredient.godown_id,
            quantity_required=ingredient.quantity_required
        )

        db.add(row)
        created.append(row)

    await db.commit()

    return {
        "message": "Ingredients added successfully",
        "count": len(created)
    }


@router.get(
    "/item/{item_id}",
    response_model=ItemRecipeResponse
)
async def get_recipe_by_item(
    item_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    # result = await db.execute(
    #     select(
    #         ItemIngredient,
    #         InventoryItem,
    #         Godown
    #     )
    #     .join(
    #         InventoryItem,
    #         InventoryItem.id == ItemIngredient.inventory_item_id
    #     )
    #     .join(
    #         Godown,
    #         Godown.id == ItemIngredient.godown_id
    #     )
    #     .where(
    #         ItemIngredient.item_id == item_id
    #     )
    # )

    result = await db.execute(
    select(
        ItemIngredient,
        InventoryItem,
        Godown
    )
    .join(
        InventoryItem,
        InventoryItem.id == ItemIngredient.inventory_item_id
    )
    .join(
        Godown,
        Godown.id == ItemIngredient.godown_id
    )
    .where(
        ItemIngredient.item_id == item_id
    )
)

    rows = result.all()

    return {
    "item_id": item.id,
    "item_name": item.name,
    "ingredients": [
        {
            "ingredient_id": recipe.id,
            "inventory_item_id": inventory.id,
            "inventory_name": inventory.name,
            "unit": inventory.unit,
            "godown_id": godown.id,
            "godown_name": godown.name,
            "quantity_required": recipe.quantity_required
        }
        for recipe, inventory, godown in rows
    ]
}


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
    ingredient = await db.get(
        ItemIngredient,
        ingredient_id
    )

    if not ingredient:
        raise HTTPException(
            status_code=404,
            detail="Ingredient not found"
        )

    ingredient.quantity_required = (
        data.quantity_required
    )

    await db.commit()
    await db.refresh(ingredient)

    return ingredient


@router.delete("/{ingredient_id}")
async def delete_ingredient(
    ingredient_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    ingredient = await db.get(
        ItemIngredient,
        ingredient_id
    )

    if not ingredient:
        raise HTTPException(
            status_code=404,
            detail="Ingredient not found"
        )

    await db.delete(ingredient)

    await db.commit()

    return {
        "message": "Ingredient removed successfully"
    }


@router.put("/item/{item_id}/ingredients")
async def replace_item_ingredients(
    item_id: int,
    data: BulkIngredientCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Delete all existing in one query (atomic)
    await db.execute(
        delete(ItemIngredient).where(ItemIngredient.item_id == item_id)
    )

    # Insert new ones
    for ingredient in data.ingredients:
        db.add(ItemIngredient(
            item_id=item_id,
            inventory_item_id=ingredient.inventory_item_id,
            godown_id=ingredient.godown_id,
            quantity_required=ingredient.quantity_required
        ))

    await db.commit()

    return {
        "message": "Ingredients replaced successfully",
        "count": len(data.ingredients)
    }