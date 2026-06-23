from fastapi import HTTPException
from sqlalchemy import select, delete

from app.accounts.ingredient.model import ItemIngredient
from app.accounts.item.model import Item
from app.accounts.inventory.model import InventoryItem, Godown


async def create_item_ingredient_service(
    data,
    db
):
    existing = await db.execute(
        select(ItemIngredient).where(
            ItemIngredient.item_id == data.item_id,
            ItemIngredient.inventory_item_id == data.inventory_item_id,
            ItemIngredient.godown_id == data.godown_id
        )
    )

    if existing.scalar_one_or_none():
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


async def bulk_create_ingredients_service(
    data,
    db
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


async def get_recipe_by_item_service(
    item_id,
    db
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

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
                "unit": inventory.display_unit,
                "quantity_required":
                    recipe.quantity_required /
                    (inventory.conversion_factor or 1),
                "godown_id": godown.id,
                "godown_name": godown.name,
            }
            for recipe, inventory, godown in rows
        ]
    }


async def update_ingredient_service(
    ingredient_id,
    data,
    db
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

    ingredient.quantity_required = data.quantity_required

    await db.commit()
    await db.refresh(ingredient)

    return ingredient


async def delete_ingredient_service(
    ingredient_id,
    db
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


async def replace_item_ingredients_service(
    item_id,
    data,
    db
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    await db.execute(
        delete(ItemIngredient).where(
            ItemIngredient.item_id == item_id
        )
    )

    for ingredient in data.ingredients:
        db.add(
            ItemIngredient(
                item_id=item_id,
                inventory_item_id=ingredient.inventory_item_id,
                godown_id=ingredient.godown_id,
                quantity_required=ingredient.quantity_required
            )
        )

    await db.commit()

    return {
        "message": "Ingredients replaced successfully",
        "count": len(data.ingredients)
    }