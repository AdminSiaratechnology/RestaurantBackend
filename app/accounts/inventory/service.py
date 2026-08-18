from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.ingredient.model import ItemIngredient
from app.accounts.inventory.model import InventoryItem
from app.accounts.deps import calculate_status
from app.core.cache import Cache


async def consume_inventory_for_item(
    db,
    item_id: int,
    quantity: float
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero"
        )

    # ---------------------------------------------------------
    # GET RECIPE INGREDIENTS
    # ---------------------------------------------------------
    result = await db.execute(
        select(ItemIngredient).where(
            ItemIngredient.item_id == item_id
        )
    )

    ingredients = result.scalars().all()

    if not ingredients:
        return

    # ---------------------------------------------------------
    # LOCK + VALIDATE ALL INVENTORY ITEMS
    #
    # FOR UPDATE prevents two simultaneous orders from
    # consuming the same stock incorrectly.
    # ---------------------------------------------------------
    inventory_items = []

    for ingredient in ingredients:

        result = await db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.id
                == ingredient.inventory_item_id
            )
            .with_for_update()
        )

        inventory = result.scalar_one_or_none()

        if not inventory:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Inventory item not found: "
                    f"{ingredient.inventory_item_id}"
                )
            )

        required_qty = (
            float(ingredient.quantity_required)
            * float(quantity)
        )

        if inventory.stock_qty < required_qty:

            factor = (
                inventory.conversion_factor
                or 1
            )

            available = (
                inventory.stock_qty / factor
            )

            unit = (
                inventory.display_unit
                or inventory.unit
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for "
                    f"{inventory.name}. "
                    f"Available: {available:g} {unit}, "
                    f"Required: "
                    f"{required_qty / factor:g} {unit}"
                )
            )

        inventory_items.append(
            (
                inventory,
                required_qty
            )
        )

    # ---------------------------------------------------------
    # DEDUCT STOCK
    # ---------------------------------------------------------
    branch_ids = set()

    for inventory, required_qty in inventory_items:

        inventory.stock_qty -= required_qty

        inventory.status = calculate_status(
            inventory.stock_qty,
            inventory.reorder_level
        )

        if inventory.branch_id:
            branch_ids.add(
                inventory.branch_id
            )

    # ---------------------------------------------------------
    # CACHE INVALIDATION
    # ---------------------------------------------------------
    for branch_id in branch_ids:

        await Cache.delete_pattern(
            f"report:{branch_id}:inventory:*"
        )