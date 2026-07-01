from fastapi import HTTPException
from sqlalchemy import select
from app.accounts.ingredient.model import ItemIngredient
from app.accounts.inventory.model import InventoryItem
from app.accounts.deps import calculate_status
from app.core.cache import Cache


async def consume_inventory_for_item(
    db,
    item_id: int,
    quantity: int
):
    result = await db.execute(
        select(ItemIngredient).where(
            ItemIngredient.item_id == item_id
        )
    )

    ingredients = result.scalars().all()

    if not ingredients:
        return

    # Validate stock first
    for ingredient in ingredients:

        inventory = await db.get(
            InventoryItem,
            ingredient.inventory_item_id
        )

        required_qty = (
            ingredient.quantity_required
            * quantity
        )

        if inventory.stock_qty < required_qty:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for "
                    f"{inventory.name}"
                )
            )

    # Deduct stock
    branch_ids = set()
    for ingredient in ingredients:

        inventory = await db.get(
            InventoryItem,
            ingredient.inventory_item_id
        )

        required_qty = (
            ingredient.quantity_required
            * quantity
        )

        inventory.stock_qty -= required_qty

        inventory.status = calculate_status(
            inventory.stock_qty,
            inventory.reorder_level
        )
        if inventory.branch_id:
            branch_ids.add(inventory.branch_id)

    for bid in branch_ids:
        await Cache.delete_pattern(f"report:{bid}:inventory:*")