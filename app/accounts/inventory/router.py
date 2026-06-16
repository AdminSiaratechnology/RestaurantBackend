
from datetime import datetime
import traceback
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.accounts.deps import calculate_status
# , get_client_if_accessible
from app.accounts.inventory.model import InventoryItem, Godown
from app.accounts.inventory.schema import InventoryCreate, InventoryResponse, StockUpdate, GodownCreate, GodownOut, GodownUpdate
from app.db.config import SessionDep
from app.accounts.deps import access_one, UserRole
from fastapi import APIRouter

router = APIRouter(
    prefix="/inventory",
    tags= ["Inventory"]
)

UNIT_MAPPING = {
    "gm": ("gm", 1),
    "kg": ("gm", 1000),

    "ml": ("ml", 1),
    "litre": ("ml", 1000),

    "piece": ("piece", 1),
    "dozen": ("piece", 12),
    "tray": ("piece", 30),
}

BASE_UNITS = {"gm", "ml", "piece"}



def convert_to_base_unit(
    unit: str,
    qty: float
):
    unit = unit.lower()

    if unit not in UNIT_MAPPING:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported unit {unit}"
        )

    base_unit, factor = UNIT_MAPPING[unit]

    return (
        base_unit,
        qty * factor,
        factor
    )





def display_unit(item, qty):
    factor = item.conversion_factor or 1
    unit = item.display_unit or item.unit
    return {
        "display_qty": qty / factor,
        "display_unit": unit
    }


def normalize_inventory_item_unit(item):
    if item.unit in BASE_UNITS:
        return

    if item.unit not in UNIT_MAPPING:
        return

    base_unit, factor = UNIT_MAPPING[item.unit]
    item.stock_qty = item.stock_qty * factor
    item.reorder_level = item.reorder_level * factor
    item.display_unit = item.display_unit or item.unit
    item.conversion_factor = factor
    item.unit = base_unit


@router.post("/create")
async def create_inventory_item(
    data: InventoryCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        data.branch_id = user.branch_id

    godown = await db.get(
        Godown,
        data.godown_id
    )

    if not godown:
        raise HTTPException(
            status_code=404,
            detail="Godown not found"
        )

    if godown.branch_id != data.branch_id:
        raise HTTPException(
            status_code=400,
            detail="Godown does not belong to selected branch"
        )

    # existing = await db.scalar(
    #     select(InventoryItem).where(
    #         InventoryItem.name == data.name,
    #         InventoryItem.godown_id == data.godown_id
    #     )
    # )

    existing = await db.scalar(
        select(InventoryItem).where(
            InventoryItem.name.ilike(data.name),
            InventoryItem.godown_id == data.godown_id
        )
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Item already exists in this godown"
        )

    unit, stock_qty, factor = convert_to_base_unit(
        data.unit,
        data.stock_qty
    )

    _, reorder_level, _ = convert_to_base_unit(
        data.unit,
        data.reorder_level
    )

    item_status = calculate_status(
        stock_qty,
        reorder_level
    )

    item = InventoryItem(
        branch_id=data.branch_id,
        godown_id=data.godown_id,

        name=data.name,
        row_category=data.row_category,

        unit=unit,
        display_unit=data.unit,
        conversion_factor=factor,
        stock_qty=stock_qty,
        reorder_level=reorder_level,

        cost_per_unit=data.cost_per_unit / factor,

        vendor_name=data.vendor_name,
        vendor_phone=data.vendor_phone,

        status=item_status
    )

    db.add(item)

    await db.commit()
    await db.refresh(item)

    return {
        "message": "Inventory item created successfully",
        "id": item.id
    }

@router.get("/list")
async def get_inventory(
    db: SessionDep,
    branch_id: int | None = None,
    godown_id: int | None = None,
    current=Depends(access_one)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            branch_id = user.branch_id

        if not branch_id:
            raise HTTPException(
                status_code=400,
                detail="branch_id is required"
            )

        query = select(InventoryItem).where(
            InventoryItem.branch_id == branch_id
        )

        if godown_id:
            query = query.where(
                InventoryItem.godown_id == godown_id
            )

        result = await db.execute(query)
        items = result.scalars().all()

        response = []

        for item in items:
            factor = item.conversion_factor or 1

            display_stock_qty = item.stock_qty / factor
            display_reorder_level = item.reorder_level / factor

            display_cost_per_unit = item.cost_per_unit * factor

            total_value = display_stock_qty * display_cost_per_unit

            response.append({
                "id": item.id,
                "name": item.name,
                "godown_id": item.godown_id,
                "row_category": item.row_category,

                "unit": item.display_unit,
                "display_unit": item.display_unit,
                "base_unit": item.unit,
                "conversion_factor": factor,

                "stock_qty": display_stock_qty,
                "reorder_level": display_reorder_level,

                "cost_per_unit": display_cost_per_unit,
                "total_value": total_value,

                "status": item.status,

                "vendor_name": item.vendor_name,
                "vendor_phone": item.vendor_phone,

                "last_restocked": item.last_restocked
            })

        return response

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/paginated")
async def get_inventory_paginated(
    db: SessionDep,
    branch_id: int | None = None,
    godown_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    cursor: int | None = None,
    limit: int = 50,
    current=Depends(access_one)
):
    """
    Cursor-paginated inventory listing.
    Returns items with id > cursor, ordered by id asc.
    Supports filtering by godown_id, status, and full-text name search.
    """
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            branch_id = user.branch_id

        if not branch_id:
            raise HTTPException(
                status_code=400,
                detail="branch_id is required"
            )

        query = select(InventoryItem).where(
            InventoryItem.branch_id == branch_id
        )

        if godown_id:
            query = query.where(InventoryItem.godown_id == godown_id)

        if status and status != "all":
            query = query.where(InventoryItem.status == status)

        if search:
            query = query.where(
                InventoryItem.name.ilike(f"%{search}%")
            )

        if cursor is not None:
            query = query.where(InventoryItem.id > cursor)

        query = query.order_by(InventoryItem.id.asc()).limit(limit)

        result = await db.execute(query)
        items = result.scalars().all()

        response = []
        for item in items:
            factor = item.conversion_factor or 1
            display_stock_qty = item.stock_qty / factor
            display_reorder_level = item.reorder_level / factor
            display_cost_per_unit = item.cost_per_unit * factor
            total_value = display_stock_qty * display_cost_per_unit

            response.append({
                "id": item.id,
                "name": item.name,
                "godown_id": item.godown_id,
                "row_category": item.row_category,

                "unit": item.display_unit,
                "display_unit": item.display_unit,
                "base_unit": item.unit,
                "conversion_factor": factor,

                "stock_qty": display_stock_qty,
                "reorder_level": display_reorder_level,

                "cost_per_unit": display_cost_per_unit,
                "total_value": total_value,

                "status": item.status,

                "vendor_name": item.vendor_name,
                "vendor_phone": item.vendor_phone,

                "last_restocked": item.last_restocked,
            })

        # Return next cursor (last item id) so client can fetch next page
        next_cursor = items[-1].id if items else None
        has_more = len(items) == limit

        return {
            "items": response,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/stats")
async def inventory_stats(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            branch_id = user.branch_id

        if not branch_id:
            raise HTTPException(400, "branch_id is required")

        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.branch_id == branch_id
            )
        )

        items = result.scalars().all()

        total_items = len(items)
        stock_value = sum(
            item.stock_qty * item.cost_per_unit
            for item in items
        )

        low_stock = sum(
            1 for item in items
            if item.status == "low_stock"
        )

        out_of_stock = sum(
            1 for item in items
            if item.status == "out_of_stock"
        )

        return {
            "total_items": total_items,
            "stock_value": stock_value,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock
        }

    except SQLAlchemyError:
        raise HTTPException(500, "Error fetching stats")



@router.put("/{item_id}")
async def update_inventory_item(
    item_id: int,
    data: InventoryCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    item = await db.get(InventoryItem, item_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    unit, stock_qty, factor = convert_to_base_unit(
        data.unit,
        data.stock_qty
    )

    _, reorder_level, _ = convert_to_base_unit(
        data.unit,
        data.reorder_level
    )

    item.name = data.name
    item.row_category = data.row_category

    item.unit = unit
    item.display_unit = data.unit
    item.conversion_factor = factor

    item.stock_qty = stock_qty
    item.reorder_level = reorder_level

    # IMPORTANT
    item.cost_per_unit = data.cost_per_unit / factor

    item.vendor_name = data.vendor_name
    item.vendor_phone = data.vendor_phone

    item.status = calculate_status(
        stock_qty,
        reorder_level
    )

    await db.commit()
    await db.refresh(item)

    return {
        "message": "Inventory updated successfully"
    }


@router.patch("/update_stock/{item_id}")
async def update_stock(
    item_id: int,
    data: StockUpdate,
    db: SessionDep,
    current=Depends(access_one)
):
    item = await db.get(
        InventoryItem,
        item_id
    )

    if not item:
        raise HTTPException(
            404,
            "Item not found"
        )

    normalize_inventory_item_unit(item)

    display_unit_value = data.unit or item.display_unit or item.unit
    quantity = data.quantity

    if quantity is None:
        quantity = data.stock_qty

    if quantity is None:
        raise HTTPException(
            400,
            "quantity or stock_qty is required"
        )

    unit, qty, factor = convert_to_base_unit(
        display_unit_value,
        quantity
    )

    if unit != item.unit:
        raise HTTPException(
            400,
            f"Unit mismatch. Inventory unit is {item.unit}"
        )

    if data.name is not None:
        item.name = data.name

    if data.row_category is not None:
        item.row_category = data.row_category

    if data.godown_id is not None:
        item.godown_id = data.godown_id

    if data.cost_per_unit is not None:
        item.cost_per_unit = data.cost_per_unit

    if data.vendor_name is not None:
        item.vendor_name = data.vendor_name

    if data.vendor_phone is not None:
        item.vendor_phone = data.vendor_phone

    item.display_unit = display_unit_value
    item.conversion_factor = factor

    if data.reorder_level is not None:
        _, reorder_level, _ = convert_to_base_unit(
            display_unit_value,
            data.reorder_level
        )
        item.reorder_level = reorder_level

    if data.operation == "add":
        item.stock_qty += qty

    elif data.operation == "subtract":
        if item.stock_qty < qty:
            raise HTTPException(
                400,
                "Insufficient stock"
            )

        item.stock_qty -= qty

    else:
        item.stock_qty = qty

    item.status = calculate_status(
        item.stock_qty,
        item.reorder_level
    )

    item.last_restocked = datetime.utcnow()

    if data.last_restocked is not None:
        item.last_restocked = data.last_restocked

    await db.commit()

    return {
        "message": "Stock updated successfully",
        "current_stock": item.stock_qty,
        "unit": item.unit
    }


@router.post("/creategodown", response_model=GodownOut, status_code=status.HTTP_201_CREATED)
async def create_godown(
    data: GodownCreate,
    db: SessionDep
):
    # Check duplicate name in same branch
    existing = await db.scalar(
        select(Godown).where(
            Godown.name == data.name,
            Godown.branch_id == data.branch_id
        )
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Godown with this name already exists"
        )

    godown = Godown(
        branch_id=data.branch_id,
        name=data.name,
        code=data.code,
        address=data.address
    )

    db.add(godown)
    await db.commit()
    await db.refresh(godown)

    return godown


@router.get("/godowns", response_model=list[GodownOut])
async def get_godowns(
    branch_id: int,
    db: SessionDep
):
    result = await db.execute(
        select(Godown).where(
            Godown.branch_id == branch_id
        )
    )

    return result.scalars().all()


@router.put("/godowns/{godown_id}", response_model=GodownOut)
async def update_godown(
    godown_id: int,
    data: GodownUpdate,
    db: SessionDep
):
    godown = await db.get(Godown, godown_id)

    if not godown:
        raise HTTPException(
            status_code=404,
            detail="Godown not found"
        )

    if data.name is not None:
        duplicate = await db.scalar(
            select(Godown).where(
                Godown.name == data.name,
                Godown.branch_id == godown.branch_id,
                Godown.id != godown_id
            )
        )

        if duplicate:
            raise HTTPException(
                status_code=400,
                detail="Godown with this name already exists"
            )

        godown.name = data.name

    if data.code is not None:
        godown.code = data.code

    if data.address is not None:
        godown.address = data.address

    await db.commit()
    await db.refresh(godown)

    return godown



@router.delete("/godowns/{godown_id}")
async def delete_godown(
    godown_id: int,
    db: SessionDep
):
    godown = await db.get(
        Godown,
        godown_id
    )

    if not godown:
        raise HTTPException(
            status_code=404,
            detail="Godown not found"
        )

    inventory_exists = await db.scalar(
        select(InventoryItem.id).where(
            InventoryItem.godown_id == godown_id
        )
    )

    if inventory_exists:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete godown "
                "because inventory items exist"
            )
        )

    await db.delete(godown)
    await db.commit()

    return {
        "message": "Godown deleted successfully"
    }




@router.get("/dashboard-graph")
async def inventory_dashboard_graph(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        branch_id = user.branch_id

    if not branch_id:
        raise HTTPException(
            status_code=400,
            detail="branch_id is required"
        )

    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.branch_id == branch_id
        )
    )

    items = result.scalars().all()

    total_items = len(items)

    in_stock = sum(
        1 for item in items
        if item.status == "in_stock"
    )

    low_stock = sum(
        1 for item in items
        if item.status == "low_stock"
    )

    out_of_stock = sum(
        1 for item in items
        if item.status == "out_of_stock"
    )

    return {
        "total_items": total_items,
        "in_stock": in_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock
    }



@router.get("/dashboard-category-graph")
async def inventory_category_graph(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.STAFF:
        branch_id = user.branch_id

    if not branch_id:
        raise HTTPException(
            status_code=400,
            detail="branch_id is required"
        )

    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.branch_id == branch_id
        )
    )

    items = result.scalars().all()

    categories = {}

    for item in items:
        category = item.row_category or "other"

        categories[category] = (
            categories.get(category, 0) + 1
        )

    return categories