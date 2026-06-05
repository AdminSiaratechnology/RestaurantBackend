from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.bom.model import MenuItemBOM
from app.accounts.deps import require_client, get_current_user, UserRole
from app.accounts.deps import access_one
from app.db.config import SessionDep
from app.accounts.ingredient.model import ItemIngredient

from app.accounts.item.model import Item
from app.accounts.inventory.model import (
    InventoryItem,
    Godown
)

from .schema import (
    BOMCreate,
    BOMUpdate,
    BOMResponse,
    BulkBOMCreate,
    ItemRecipeResponse
)

router = APIRouter(
    prefix="/bom",
    tags=["BOM"]
)



@router.post(
    "/",
    response_model=BOMResponse
)
async def create_bom(
    data: BOMCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    bom = MenuItemBOM(
        menu_item_id=data.menu_item_id,
        inventory_item_id=data.inventory_item_id,
        godown_id=data.godown_id,
        qty_required=data.qty_required
    )

    db.add(bom)

    await db.commit()
    await db.refresh(bom)

    return bom



@router.post("/bulk")
async def bulk_create_bom(
    data: BulkBOMCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    rows = []

    for ingredient in data.ingredients:

        bom = MenuItemBOM(
            menu_item_id=data.menu_item_id,
            inventory_item_id=ingredient.inventory_item_id,
            godown_id=ingredient.godown_id,
            qty_required=ingredient.qty_required
        )

        db.add(bom)
        rows.append(bom)

    await db.commit()

    return {
        "message": "BOM created successfully",
        "count": len(rows)
    }



@router.get(
    "/item/{item_id}",
    response_model=ItemRecipeResponse
)
async def get_recipe(
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

    result = await db.execute(
        select(
            MenuItemBOM,
            InventoryItem,
            Godown
        )
        .join(
            InventoryItem,
            InventoryItem.id ==
            MenuItemBOM.inventory_item_id
        )
        .join(
            Godown,
            Godown.id ==
            MenuItemBOM.godown_id
        )
        .where(
            MenuItemBOM.menu_item_id ==
            item_id
        )
    )

    rows = result.all()

    return {
        "item_id": item.id,
        "item_name": item.name,
        "ingredients": [
            {
                "bom_id": bom.id,
                "inventory_item_id": inventory.id,
                "inventory_name": inventory.name,
                "unit": inventory.unit,
                "godown_id": godown.id,
                "godown_name": godown.name,
                "qty_required": bom.qty_required
            }
            for bom, inventory, godown in rows
        ]
    }




@router.patch(
    "/{bom_id}",
    response_model=BOMResponse
)
async def update_bom(
    bom_id: int,
    data: BOMUpdate,
    db: SessionDep,
    current=Depends(access_one)
):
    bom = await db.get(
        MenuItemBOM,
        bom_id
    )

    if not bom:
        raise HTTPException(
            status_code=404,
            detail="BOM not found"
        )

    bom.qty_required = data.qty_required

    await db.commit()
    await db.refresh(bom)

    return bom




@router.delete("/{bom_id}")
async def delete_bom(
    bom_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    bom = await db.get(
        MenuItemBOM,
        bom_id
    )

    if not bom:
        raise HTTPException(
            status_code=404,
            detail="BOM not found"
        )

    await db.delete(bom)
    await db.commit()

    return {
        "message": "BOM removed successfully"
    }