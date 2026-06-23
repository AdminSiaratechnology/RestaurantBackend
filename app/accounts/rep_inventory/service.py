# =========================================================
# app/accounts/rep_inventory/service.py
# =========================================================

from sqlalchemy import select, func

from app.accounts.inventory.model import InventoryItem

from app.accounts.rep_inventory.schema import (
    InventoryDashboardResponse,
    LowStockItem,
    CategoryStockValue
)


async def get_inventory_dashboard_service(
    db,
    branch_id: int
):
    total_items = await db.scalar(
        select(
            func.count(InventoryItem.id)
        ).where(
            InventoryItem.branch_id == branch_id
        )
    ) or 0

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

    low_stock_items = await db.scalar(
        select(
            func.count(InventoryItem.id)
        ).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.stock_qty > 0,
            InventoryItem.stock_qty <= InventoryItem.reorder_level
        )
    ) or 0

    out_of_stock_items = await db.scalar(
        select(
            func.count(InventoryItem.id)
        ).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.stock_qty <= 0
        )
    ) or 0

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




from fastapi import HTTPException
from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.inventory.model import InventoryItem
from app.accounts.enum import UserRole


async def get_inventory_dashboard_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    response = {
        "total_items": 0,
        "stock_value": 0,
        "low_stock_items": 0,
        "out_of_stock_items": 0,
        "branches": []
    }

    for branch in branches:

        total_items = await db.scalar(
            select(
                func.count(InventoryItem.id)
            ).where(
                InventoryItem.branch_id == branch.id
            )
        ) or 0

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
                InventoryItem.branch_id == branch.id
            )
        ) or 0

        low_stock_items = await db.scalar(
            select(
                func.count(InventoryItem.id)
            ).where(
                InventoryItem.branch_id == branch.id,
                InventoryItem.stock_qty > 0,
                InventoryItem.stock_qty <= InventoryItem.reorder_level
            )
        ) or 0

        out_of_stock_items = await db.scalar(
            select(
                func.count(InventoryItem.id)
            ).where(
                InventoryItem.branch_id == branch.id,
                InventoryItem.stock_qty <= 0
            )
        ) or 0

        low_stock_result = await db.execute(
            select(
                InventoryItem.id,
                InventoryItem.name,
                InventoryItem.stock_qty,
                InventoryItem.reorder_level,
                InventoryItem.display_unit
            )
            .where(
                InventoryItem.branch_id == branch.id,
                InventoryItem.stock_qty > 0,
                InventoryItem.stock_qty <= InventoryItem.reorder_level
            )
            .order_by(
                InventoryItem.stock_qty.asc()
            )
        )

        low_stock_list = [
            {
                "item_id": row.id,
                "item_name": row.name,
                "current_stock": row.stock_qty,
                "reorder_level": row.reorder_level,
                "unit": row.display_unit
            }
            for row in low_stock_result.all()
        ]

        category_result = await db.execute(
            select(
                InventoryItem.row_category,
                func.sum(
                    InventoryItem.stock_qty *
                    InventoryItem.cost_per_unit
                ).label("stock_value")
            )
            .where(
                InventoryItem.branch_id == branch.id
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
            {
                "category_name": row.row_category,
                "stock_value": round(
                    float(row.stock_value or 0),
                    2
                )
            }
            for row in category_result.all()
        ]

        response["total_items"] += total_items
        response["stock_value"] += float(stock_value)
        response["low_stock_items"] += low_stock_items
        response["out_of_stock_items"] += out_of_stock_items

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_items": total_items,
            "stock_value": round(
                float(stock_value),
                2
            ),
            "low_stock_items": low_stock_items,
            "out_of_stock_items": out_of_stock_items,
            "low_stock_list": low_stock_list,
            "category_stock_value": category_stock_value
        })

    response["stock_value"] = round(
        response["stock_value"],
        2
    )

    return response