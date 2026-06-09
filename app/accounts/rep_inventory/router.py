from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.db.config import SessionDep

from app.accounts.inventory.model import InventoryItem

from app.accounts.rep_inventory.schema import (
    InventoryDashboardResponse,
    LowStockItem,
    CategoryStockValue
)

router = APIRouter(
    prefix="/reports/inventory",
    tags=["Inventory Reports"]
)


@router.get(
    "/dashboard-summary",
    response_model=InventoryDashboardResponse
)
async def get_inventory_dashboard(
    db: SessionDep,
    branch_id: int = Query(...)
):

    # ==========================================
    # TOTAL ITEMS
    # ==========================================

    total_items = await db.scalar(
        select(
            func.count(
                InventoryItem.id
            )
        ).where(
            InventoryItem.branch_id == branch_id
        )
    ) or 0

    # ==========================================
    # STOCK VALUE
    # Formula:
    # stock_qty * cost_per_unit
    # ==========================================

    stock_value = await db.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(
                        InventoryItem.stock_qty,
                        0
                    )
                    *
                    func.coalesce(
                        InventoryItem.cost_per_unit,
                        0
                    )
                ),
                0
            )
        ).where(
            InventoryItem.branch_id == branch_id
        )
    ) or 0

    # ==========================================
    # LOW STOCK COUNT
    # ==========================================

    low_stock_items = await db.scalar(
        select(
            func.count(
                InventoryItem.id
            )
        ).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.stock_qty > 0,
            InventoryItem.stock_qty <= InventoryItem.reorder_level
        )
    ) or 0

    # ==========================================
    # OUT OF STOCK COUNT
    # ==========================================

    out_of_stock_items = await db.scalar(
        select(
            func.count(
                InventoryItem.id
            )
        ).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.stock_qty <= 0
        )
    ) or 0

    # ==========================================
    # LOW STOCK LIST
    # ==========================================

    result = await db.execute(
        select(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.stock_qty,
            InventoryItem.reorder_level,
            InventoryItem.display_unit
        )
        .where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.stock_qty > 0,
            InventoryItem.stock_qty <= InventoryItem.reorder_level
        )
        .order_by(
            InventoryItem.stock_qty.asc()
        )
    )

    low_stock_list = [
        LowStockItem(
            item_id=row.id,
            item_name=row.name,
            current_stock=row.stock_qty,
            reorder_level=row.reorder_level,
            unit=row.display_unit
        )
        for row in result.all()
    ]

    # ==========================================
    # CATEGORY STOCK VALUE CHART
    # ==========================================

    category_result = await db.execute(
        select(
            InventoryItem.row_category,
            func.sum(
                InventoryItem.stock_qty *
                InventoryItem.cost_per_unit
            ).label("stock_value")
        )
        .where(
            InventoryItem.branch_id == branch_id
        )
        .group_by(
            InventoryItem.row_category
        )
        .order_by(
            func.sum(
                InventoryItem.stock_qty *
                InventoryItem.cost_per_unit
            ).desc()
        )
    )

    category_stock_value = [
        CategoryStockValue(
            category_name=row.row_category,
            stock_value=round(
                float(row.stock_value or 0),
                2
            )
        )
        for row in category_result.all()
    ]

    return InventoryDashboardResponse(
        total_items=total_items,
        stock_value=round(
            float(stock_value),
            2
        ),
        low_stock_items=low_stock_items,
        out_of_stock_items=out_of_stock_items,
        low_stock_list=low_stock_list,
        category_stock_value=category_stock_value
    )