
from datetime import datetime
import traceback
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.accounts.branch import router
from app.accounts.deps import calculate_status, get_client_if_accessible
from app.accounts.inventory.model import InventoryItem
from app.accounts.inventory.schema import InventoryCreate
from app.db.config import SessionDep
from app.accounts.deps import access_four, UserRole
from fastapi import APIRouter

router = APIRouter(
    prefix="/inventory",
    tags= ["Inventory"]
)


@router.post("/create")
async def create_inventory_item(
    data: InventoryCreate,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        await get_client_if_accessible(data.client_id, db, current)

        status = calculate_status(data.stock_qty, data.reorder_level)

        item = InventoryItem(
            client_id=data.client_id,
            branch_id=data.branch_id,
            name=data.name,
            row_category=data.row_category,
            unit=data.unit,
            stock_qty=data.stock_qty,
            reorder_level=data.reorder_level,
            cost_per_unit=data.cost_per_unit,
            vendor_name=data.vendor_name,
            vendor_phone=data.vendor_phone,
            status=status,
            last_restocked=data.last_restocked
        )

        db.add(item)
        await db.commit()
        await db.refresh(item)

        return {"message": "Item created", "id": item.id}

    except HTTPException as e:
        await db.rollback()
        raise e
    # except SQLAlchemyError:
    #     await db.rollback()
    #     raise HTTPException(500, "Database error")


    except SQLAlchemyError as e:
        await db.rollback()
        # print("❌ DB ERROR:", str(e))
        # traceback.print_exc()
        raise HTTPException(500, f"Database error: {str(e)}")


@router.get("/list")
async def get_inventory(
    client_id: int,
    branch_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        await get_client_if_accessible(client_id, db, current)

        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.client_id == client_id,
                InventoryItem.branch_id == branch_id
            )
        )

        items = result.scalars().all()

        response = []

        for i in items:
            total_value = i.stock_qty * i.cost_per_unit

            response.append({
                "id": i.id,
                "name": i.name,
                "row_category": i.row_category,
                "unit": i.unit,
                "stock_qty": i.stock_qty,
                "reorder_level": i.reorder_level,
                "cost_per_unit": i.cost_per_unit,
                "total_value": total_value,
                "status": i.status,
                "vendor_name": i.vendor_name,
                "vendor_phone": i.vendor_phone,
                "last_restocked": i.last_restocked
            })

        return response

    except SQLAlchemyError:
        raise HTTPException(500, "Error fetching inventory")
    


@router.get("/stats")
async def inventory_stats(
    client_id: int,
    branch_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        await get_client_if_accessible(client_id, db, current)

        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.client_id == client_id,
                InventoryItem.branch_id == branch_id
            )
        )

        items = result.scalars().all()

        total_items = len(items)
        stock_value = sum(i.stock_qty * i.cost_per_unit for i in items)
        low_stock = sum(1 for i in items if i.status == "low_stock")
        out_of_stock = sum(1 for i in items if i.status == "out_of_stock")

        return {
            "total_items": total_items,
            "stock_value": stock_value,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock
        }

    except SQLAlchemyError:
        raise HTTPException(500, "Error fetching stats")
    

# @router.patch("/update_stock/{item_id}")
# async def update_stock(
#     item_id: int,
#     stock_qty: float,
#     db: SessionDep,
#     current=Depends(access_four)
# ):
#     try:
#         item = await db.get(InventoryItem, item_id)

#         if not item:
#             raise HTTPException(404, "Item not found")

#         await get_client_if_accessible(item.client_id, db, current)

#         item.stock_qty = stock_qty
#         item.status = calculate_status(stock_qty, item.reorder_level)
#         item.last_restocked = datetime.utcnow()

#         await db.commit()

#         return {"message": "Stock updated"}

#     except HTTPException as e:
#         await db.rollback()
#         raise e
#     except SQLAlchemyError:
#         await db.rollback()
#         raise HTTPException(500, "Database error")

from pydantic import BaseModel

class StockUpdate(BaseModel):
    stock_qty: float

@router.patch("/update_stock/{item_id}")
async def update_stock(
    item_id: int,
    data: StockUpdate,   # 👈 accept body
    db: SessionDep,
    current=Depends(access_four)
):
    item = await db.get(InventoryItem, item_id)

    if not item:
        return {"message": "Item not found"}

    await get_client_if_accessible(item.client_id, db, current)

    item.stock_qty = data.stock_qty
    item.status = calculate_status(data.stock_qty, item.reorder_level)
    item.last_restocked = datetime.utcnow()

    await db.commit()

    return {"message": "Stock updated"}
