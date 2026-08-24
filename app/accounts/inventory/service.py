from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.ingredient.model import ItemIngredient
from app.accounts.inventory.model import InventoryItem
from app.accounts.deps import calculate_status
from app.core.cache import Cache


async def consume_inventory_for_item(
    db,
    item_id: int,
    quantity: float,
):
    """
    Consume inventory stock for a menu item based on its recipe.

    IMPORTANT:
    - All required inventory rows are locked in deterministic ID order.
    - Duplicate recipe ingredients pointing to the same inventory item
      are aggregated before stock validation/deduction.
    - All stock validation happens BEFORE any stock is modified.
    - No commit is performed here. The caller owns the transaction.
    - Cache invalidation is intentionally performed after DB flush.
    """

    # ============================================================
    # 1. VALIDATE ORDER QUANTITY
    # ============================================================

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Quantity must be a valid number",
        )

    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero",
        )

    # ============================================================
    # 2. GET RECIPE INGREDIENTS
    # ============================================================

    result = await db.execute(
        select(ItemIngredient).where(
            ItemIngredient.item_id == item_id
        )
    )

    ingredients = result.scalars().all()

    if not ingredients:
        return {
            "item_id": item_id,
            "quantity": quantity,
            "consumed": False,
            "message": "No recipe ingredients found",
            "branch_ids": set(),
        }

    # ============================================================
    # 3. AGGREGATE INGREDIENT REQUIREMENTS
    #
    # If the same inventory item is used more than once in a recipe,
    # combine it into one requirement.
    #
    # Example:
    #
    # inventory_item_id = 10 -> 20 gm
    # inventory_item_id = 10 -> 30 gm
    #
    # becomes:
    #
    # inventory_item_id = 10 -> 50 gm
    # ============================================================

    required_by_inventory_id = defaultdict(float)

    for ingredient in ingredients:

        inventory_item_id = ingredient.inventory_item_id

        if not inventory_item_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid recipe configuration for item "
                    f"{item_id}: inventory_item_id is missing"
                ),
            )

        ingredient_quantity = float(
            ingredient.quantity_required or 0
        )

        if ingredient_quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid recipe quantity for inventory item "
                    f"{inventory_item_id}. "
                    f"Quantity required must be greater than zero."
                ),
            )

        required_qty = (
            ingredient_quantity * quantity
        )

        required_by_inventory_id[
            inventory_item_id
        ] += required_qty

    # ============================================================
    # 4. GET ALL INVENTORY IDS
    # ============================================================

    inventory_ids = sorted(
        required_by_inventory_id.keys()
    )

    if not inventory_ids:
        return {
            "item_id": item_id,
            "quantity": quantity,
            "consumed": False,
            "message": "No valid inventory requirements found",
            "branch_ids": set(),
        }

    # ============================================================
    # 5. LOCK ALL INVENTORY ROWS IN ONE QUERY
    #
    # THIS IS THE IMPORTANT DEADLOCK FIX.
    #
    # Every transaction locks inventory rows using the SAME ORDER:
    #
    # ORDER BY inventory.id
    #
    # Therefore:
    #
    # Transaction A:
    #   lock 10
    #   lock 20
    #
    # Transaction B:
    #   waits for 10
    #
    # instead of:
    #
    # Transaction A:
    #   lock 10
    #   waits for 20
    #
    # Transaction B:
    #   lock 20
    #   waits for 10
    # ============================================================

    result = await db.execute(
        select(InventoryItem)
        .where(
            InventoryItem.id.in_(inventory_ids)
        )
        .order_by(
            InventoryItem.id.asc()
        )
        .with_for_update()
    )

    locked_inventory_items = result.scalars().all()

    # ============================================================
    # 6. CREATE INVENTORY LOOKUP
    # ============================================================

    inventory_by_id = {
        inventory.id: inventory
        for inventory in locked_inventory_items
    }

    # ============================================================
    # 7. VALIDATE THAT ALL INVENTORY ITEMS EXIST
    # ============================================================

    missing_inventory_ids = [
        inventory_id
        for inventory_id in inventory_ids
        if inventory_id not in inventory_by_id
    ]

    if missing_inventory_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                "Inventory item(s) not found: "
                + ", ".join(
                    str(value)
                    for value in missing_inventory_ids
                )
            ),
        )

    # ============================================================
    # 8. VALIDATE ALL STOCK BEFORE MODIFYING ANY STOCK
    # ============================================================

    inventory_consumption = []

    for inventory_id in inventory_ids:

        inventory = inventory_by_id[inventory_id]

        required_qty = required_by_inventory_id[
            inventory_id
        ]

        current_stock = float(
            inventory.stock_qty or 0
        )

        if current_stock < required_qty:

            conversion_factor = float(
                inventory.conversion_factor or 1
            )

            if conversion_factor <= 0:
                conversion_factor = 1

            available = (
                current_stock / conversion_factor
            )

            required_display_qty = (
                required_qty / conversion_factor
            )

            unit = (
                inventory.display_unit
                or inventory.unit
                or "unit"
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for "
                    f"{inventory.name}. "
                    f"Available: {available:g} {unit}, "
                    f"Required: "
                    f"{required_display_qty:g} {unit}"
                ),
            )

        inventory_consumption.append(
            (
                inventory,
                required_qty,
            )
        )

    # ============================================================
    # 9. DEDUCT STOCK
    #
    # At this point ALL inventory rows are locked and ALL stock
    # requirements have already passed validation.
    # ============================================================

    branch_ids = set()

    for inventory, required_qty in inventory_consumption:

        current_stock = float(
            inventory.stock_qty or 0
        )

        new_stock = (
            current_stock - required_qty
        )

        # Prevent tiny floating-point negative values.
        if -0.000001 < new_stock < 0:
            new_stock = 0.0

        inventory.stock_qty = max(
            0.0,
            new_stock,
        )

        inventory.status = calculate_status(
            inventory.stock_qty,
            inventory.reorder_level,
        )

        if inventory.branch_id:
            branch_ids.add(
                inventory.branch_id
            )

    # ============================================================
    # 10. FLUSH CHANGES
    #
    # Flush sends UPDATE statements while keeping the transaction
    # controlled by the caller.
    #
    # DO NOT COMMIT HERE.
    # ============================================================

    await db.flush()

    # ============================================================
    # 11. CACHE INVALIDATION
    #
    # If your caller commits AFTER this function, cache invalidation
    # here can theoretically race with a cache read before commit.
    #
    # For maximum correctness, prefer doing this AFTER db.commit()
    # in the caller.
    #
    # We return branch_ids so the caller can invalidate after commit.
    # ============================================================

    return {
        "item_id": item_id,
        "quantity": quantity,
        "consumed": True,
        "branch_ids": branch_ids,
        "consumed_items": [
            {
                "inventory_item_id": inventory.id,
                "inventory_name": inventory.name,
                "quantity_consumed": required_qty,
                "remaining_stock": float(
                    inventory.stock_qty or 0
                ),
            }
            for inventory, required_qty
            in inventory_consumption
        ],
    }