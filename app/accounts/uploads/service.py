"""
app/accounts/uploads/service.py

Generic Bulk Upload Framework — Production Ready
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.bill.enum import PaymentStatus
from app.accounts.bill.model import Bill
from app.accounts.branch.model import Branch
from app.accounts.category.model import Category
from app.accounts.ingredient.model import ItemIngredient
from app.accounts.inventory.model import Godown, InventoryItem
from app.accounts.item.enum import FoodType
from app.accounts.item.model import Item
from app.accounts.order.model import Order, OrderItem
from app.accounts.payment.model import Payment
from app.accounts.pricing.model import Pricing


# ============================================================================
# TEMPLATE & CONFIG DEFINITIONS
# ============================================================================

TEMPLATES: dict[str, dict[str, list[dict]]] = {

    # ------------------------------------------------------------------------
    # MENU
    # ------------------------------------------------------------------------
    "menu": {
        "Menu_Items": [
            {
                "Name": "Veg Burger",
                "Category": "Fast Food",
                "Branch Code": "BR001",
                "Food Type": "veg",
                "Active": True,
            }
        ],

        "Pricing": [
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Price": 120,
                "Cost Price": 70,
                "Discount": 10,
                "Tax": 5,
                "CGST": 2.5,
                "SGST": 2.5,
                "Calories": 350,
                "Active": True,
            }
        ],

        "BOM": [
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Burger Bun",
                "Godown": "Main Store",
                "Quantity": 1,
            },
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Veg Patty",
                "Godown": "Main Store",
                "Quantity": 1,
            },
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Mayonnaise",
                "Godown": "Main Store",
                "Quantity": 20,
            },
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Lettuce",
                "Godown": "Main Store",
                "Quantity": 15,
            },
        ],
    },

    # ------------------------------------------------------------------------
    # INVENTORY
    # ------------------------------------------------------------------------
    "inventory": {
        "Inventory_Items": [
            {
                "Name": "Burger Bun",
                "Branch Code": "BR001",
                "Godown": "Main Store",
                "Category": "dry",
                "Unit": "kg",
                "Display Unit": "piece",
                "Conversion Factor": 1.0,
                "Stock Qty": 100.0,
                "Reorder Level": 20.0,
                "Cost Per Unit": 5.50,
                "Vendor Name": "Fresh Farms",
                "Vendor Phone": "9876543210",
                "Status": "in_stock",
            }
        ]
    },

    # ------------------------------------------------------------------------
    # CATEGORY
    # ------------------------------------------------------------------------
    "category": {
        "Categories": [
            {
                "Name": "Fast Food",
                "Branch Code": "BR001",
                "Active": True,
            }
        ]
    },

    # ------------------------------------------------------------------------
    # BILL
    # ------------------------------------------------------------------------
    "bill": {
        "Bills": [
            {
                "Invoice No": "INV-2025-001",
                "Branch Code": "BR001",
                "Order Type": "dine_in",
                "Customer Name": "John Doe",
                "Customer Phone": "9876543210",
                "Payment Status": "paid",
                "Payment Method": "cash",
                "Subtotal": 240.0,
                "CGST %": 2.5,
                "CGST Amount": 6.0,
                "SGST %": 2.5,
                "SGST Amount": 6.0,
                "Service Charge %": 5.0,
                "Service Charge Amount": 12.0,
                "Tax Total": 12.0,
                "Discount Amount": 10.0,
                "Round Off Amount": 0.5,
                "Grand Total": 254.5,
                "Paid Amount": 254.5,
                "Due Amount": 0.0,
                "Offer Discount": 0.0,
                "Final Amount": 254.5,
                "Notes": "Extra napkins requested",
                "Footer Message": "Thank you for dining with us!",
                "Billed At": "2025-06-27 13:00:00",
            }
        ]
    },
}


# ============================================================================
# VALID VALUES
# ============================================================================

# IMPORTANT:
# This was missing in the old code and caused:
# NameError: name '_VALID_STATUS' is not defined
#
# Keep these values synchronized with the InventoryItem.status column/enum.
_VALID_STATUS = {
    "in_stock",
    "out_of_stock",
    "low_stock",
    "discontinued",
}


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class SheetConfig:
    """Describes a single sheet within a module's upload file."""

    name: str
    required_columns: list[str]


@dataclass
class ModuleConfig:
    """
    Full configuration for one uploadable module.

    sheets  — ordered list of SheetConfig; all must be present in the file.
    handler — async callable that owns the module's business logic.
    """

    sheets: list[SheetConfig]
    handler: Callable


# ============================================================================
# UPLOAD CONFIGURATION
# ============================================================================

UPLOAD_CONFIG: dict[str, ModuleConfig] = {

    # ------------------------------------------------------------------------
    # MENU
    # ------------------------------------------------------------------------
    "menu": ModuleConfig(
        sheets=[
            SheetConfig(
                "Menu_Items",
                [
                    "Name",
                    "Category",
                    "Branch Code",
                    "Food Type",
                    "Active",
                ],
            ),
            SheetConfig(
                "Pricing",
                [
                    "Menu Item",
                    "Branch Code",
                    "Price",
                    "Cost Price",
                    "Discount",
                    "Tax",
                    "CGST",
                    "SGST",
                    "Calories",
                    "Active",
                ],
            ),
            SheetConfig(
                "BOM",
                [
                    "Menu Item",
                    "Branch Code",
                    "Inventory Item",
                    "Godown",
                    "Quantity",
                ],
            ),
        ],
        handler=None,
    ),

    # ------------------------------------------------------------------------
    # INVENTORY
    # ------------------------------------------------------------------------
    "inventory": ModuleConfig(
        sheets=[
            SheetConfig(
                "Inventory_Items",
                [
                    "Name",
                    "Branch Code",
                    "Unit",
                ],
            )
        ],
        handler=None,
    ),

    # ------------------------------------------------------------------------
    # CATEGORY
    # ------------------------------------------------------------------------
    "category": ModuleConfig(
        sheets=[
            SheetConfig(
                "Categories",
                [
                    "Name",
                    "Branch Code",
                    "Active",
                ],
            )
        ],
        handler=None,
    ),
}


# ============================================================================
# RESULT TYPE
# ============================================================================

@dataclass
class UploadResult:
    message: str = "Upload successful"
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            **self.counts,
        }


# ============================================================================
# SHARED HELPERS
# ============================================================================

def _safe_str(val: Any) -> str:
    """
    Convert Excel cell value to a clean string.

    NaN / None -> ""
    """
    return str(val).strip() if pd.notna(val) else ""


def _safe_float(val: Any, field_name: str) -> float:
    """
    Safely convert Excel value to float.
    """

    # Empty Excel values should use 0
    if val is None or pd.isna(val) or str(val).strip() == "":
        return 0.0

    try:
        result = float(val)
    except (TypeError, ValueError):

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid numeric value for '{field_name}': "
                f"{val!r}"
            ),
        )

    if result < 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{field_name}' cannot be negative. "
                f"Got {result}."
            ),
        )

    return result


def _safe_bool(val: Any) -> bool:

    if isinstance(val, bool):
        return val

    if val is None or pd.isna(val):
        return False

    return str(val).strip().lower() in (
        "true",
        "1",
        "yes",
        "y",
        "on",
    )


def _safe_food_type(
    val: Any,
    row_num: int,
) -> FoodType:
    """
    Safely convert a value to FoodType enum.
    """

    if pd.isna(val) or not str(val).strip():
        return FoodType.veg

    normalized = (
        str(val)
        .strip()
        .lower()
        .replace(" ", "_")
    )

    if normalized in [
        "veg",
        "vegetarian",
    ]:
        return FoodType.veg

    if normalized in [
        "non_veg",
        "nonveg",
        "non-veg",
        "non vegetarian",
        "non-vegetarian",
    ]:
        return FoodType.non_veg

    if normalized in [
        "egg",
        "eggetarian",
    ]:
        return FoodType.egg

    try:
        return FoodType(normalized)

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Row {row_num}: Invalid Food Type "
                f"'{val}'. Allowed values: "
                f"veg, non_veg, egg."
            ),
        )


def _safe_inventory_status(
    val: Any,
    row_num: int,
) -> str:
    """
    Normalize and validate inventory status.

    Accepted examples:

        in_stock
        In Stock
        IN STOCK
        in-stock
        instock

        out_of_stock
        Out Of Stock
        out-of-stock
        outofstock

        low_stock
        Low Stock
        low-stock
        lowstock

        discontinued
        Discontinued
    """

    # Empty status defaults to in_stock.
    if val is None or pd.isna(val):
        return "in_stock"

    raw = str(val).strip()

    if not raw:
        return "in_stock"

    normalized = (
        raw
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "instock": "in_stock",
        "in_stock": "in_stock",

        "outofstock": "out_of_stock",
        "out_of_stock": "out_of_stock",

        "lowstock": "low_stock",
        "low_stock": "low_stock",

        "discontinued": "discontinued",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    if normalized not in _VALID_STATUS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Row {row_num}: Invalid inventory Status "
                f"'{raw}'. Allowed values: "
                f"{sorted(_VALID_STATUS)}"
            ),
        )

    return normalized


def _auto_width_excel(
    writer: pd.ExcelWriter,
    sheet_name: str,
) -> None:

    ws = writer.sheets[sheet_name]

    for col in ws.columns:

        max_len = max(
            len(str(cell.value))
            if cell.value is not None
            else 0
            for cell in col
        )

        ws.column_dimensions[
            col[0].column_letter
        ].width = max_len + 5


# ============================================================================
# SHARED DB LOADERS
# ============================================================================

async def _load_branches(
    db: AsyncSession,
    client_id: int,
) -> dict[str, Branch]:

    result = await db.execute(
        select(Branch).where(
            Branch.client_id == client_id
        )
    )

    return {
        b.branch_code.strip().upper(): b
        for b in result.scalars().all()
    }


async def _load_categories(
    db: AsyncSession,
    client_id: int,
) -> dict[tuple[str, int], Category]:

    result = await db.execute(
        select(Category).where(
            Category.client_id == client_id
        )
    )

    return {
        (
            c.name.strip().lower(),
            c.branch_id,
        ): c
        for c in result.scalars().all()
    }


async def _load_existing_items(
    db: AsyncSession,
    client_id: int,
) -> dict[tuple[str, int], Item]:

    result = await db.execute(
        select(Item).where(
            Item.client_id == client_id
        )
    )

    return {
        (
            i.name.strip().lower(),
            i.branch_id,
        ): i
        for i in result.scalars().all()
    }


async def _load_inventory_items(
    db: AsyncSession,
    branch_ids: list[int],
) -> dict[tuple[str, int], InventoryItem]:

    if not branch_ids:
        return {}

    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.branch_id.in_(branch_ids)
        )
    )

    return {
        (
            iv.name.strip().lower(),
            iv.branch_id,
        ): iv
        for iv in result.scalars().all()
    }


async def _load_godowns(
    db: AsyncSession,
    branch_ids: list[int],
) -> dict[tuple[str, int], Godown]:

    if not branch_ids:
        return {}

    result = await db.execute(
        select(Godown).where(
            Godown.branch_id.in_(branch_ids)
        )
    )

    return {
        (
            g.name.strip().lower(),
            g.branch_id,
        ): g
        for g in result.scalars().all()
    }


async def _load_existing_pricings(
    db: AsyncSession,
    client_id: int,
) -> dict[tuple[int, int], Pricing]:

    result = await db.execute(
        select(Pricing).where(
            Pricing.client_id == client_id
        )
    )

    return {
        (
            p.item_id,
            p.branch_id,
        ): p
        for p in result.scalars().all()
    }


async def _load_existing_bom(
    db: AsyncSession,
) -> dict[tuple[int, int, int], ItemIngredient]:

    result = await db.execute(
        select(ItemIngredient)
    )

    return {
        (
            bi.item_id,
            bi.inventory_item_id,
            bi.godown_id,
        ): bi
        for bi in result.scalars().all()
    }


# ============================================================================
# AUTO-CREATE HELPERS
# ============================================================================

async def _find_or_create_godown(
    db: AsyncSession,
    godown_name: str,
    branch_id: int,
    godowns_map: dict[tuple[str, int], Godown],
    counters: dict[str, int],
) -> Godown:

    key = (
        godown_name.strip().lower(),
        branch_id,
    )

    godown = godowns_map.get(key)

    if godown is not None:

        counters["godowns_skipped"] = (
            counters.get("godowns_skipped", 0) + 1
        )

        return godown

    godown = Godown(
        name=godown_name.strip(),
        branch_id=branch_id,
    )

    db.add(godown)

    await db.flush()

    godowns_map[key] = godown

    counters["godowns_created"] = (
        counters.get("godowns_created", 0) + 1
    )

    return godown


async def _find_or_create_category(
    db: AsyncSession,
    category_name: str,
    branch_id: int,
    client_id: int,
    categories_map: dict[tuple[str, int], Category],
    counters: dict[str, int],
) -> Category:

    key = (
        category_name.strip().lower(),
        branch_id,
    )

    category = categories_map.get(key)

    if category is not None:

        counters["categories_skipped"] = (
            counters.get("categories_skipped", 0) + 1
        )

        return category

    category = Category(
        name=category_name.strip(),
        branch_id=branch_id,
        client_id=client_id,
    )

    db.add(category)

    await db.flush()

    categories_map[key] = category

    counters["categories_created"] = (
        counters.get("categories_created", 0) + 1
    )

    return category


# ============================================================================
# MENU PROCESSOR
# ============================================================================

async def _process_menu(
    db: AsyncSession,
    sheets: dict[str, pd.DataFrame],
    client_id: int,
) -> UploadResult:

    menu_df = sheets["Menu_Items"]
    pricing_df = sheets["Pricing"]
    bom_df = sheets["BOM"]

    branches_map = await _load_branches(
        db,
        client_id,
    )

    categories_map = await _load_categories(
        db,
        client_id,
    )

    items_map = await _load_existing_items(
        db,
        client_id,
    )

    counters: dict[str, int] = {
        "categories_created": 0,
        "categories_skipped": 0,
        "godowns_created": 0,
        "godowns_skipped": 0,
        "items_created": 0,
        "items_updated": 0,
        "pricing_created": 0,
        "pricing_updated": 0,
        "bom_created": 0,
        "bom_updated": 0,
        "errors": 0,
    }

    new_items: dict[
        tuple[str, int],
        Item,
    ] = {}

    # ------------------------------------------------------------------------
    # PHASE 1: MENU ITEMS
    # ------------------------------------------------------------------------

    for idx, row in menu_df.iterrows():

        name = _safe_str(
            row.get("Name")
        )

        branch_code = _safe_str(
            row.get("Branch Code")
        ).upper()

        category_name = _safe_str(
            row.get("Category")
        )

        food_type = _safe_food_type(
            row.get("Food Type"),
            idx + 2,
        )

        if not name:
            continue

        if not branch_code:
            raise HTTPException(
                400,
                f"Row {idx + 2}: "
                f"'Branch Code' cannot be empty.",
            )

        if not category_name:
            raise HTTPException(
                400,
                f"Row {idx + 2}: "
                f"'Category' cannot be empty.",
            )

        branch = branches_map.get(
            branch_code
        )

        if branch is None:
            raise HTTPException(
                400,
                f"Branch '{branch_code}' not found.",
            )

        category = await _find_or_create_category(
            db=db,
            category_name=category_name,
            branch_id=branch.id,
            client_id=client_id,
            categories_map=categories_map,
            counters=counters,
        )

        key = (
            name.lower(),
            branch.id,
        )

        existing_item = items_map.get(key)

        if existing_item:

            existing_item.category_id = category.id
            existing_item.food_type = food_type
            existing_item.is_active = _safe_bool(
                row.get("Active", True)
            )

            counters["items_updated"] += 1

            continue

        if key in new_items:

            counters["items_updated"] += 1

            continue

        item = Item(
            name=name,
            category_id=category.id,
            branch_id=branch.id,
            client_id=client_id,
            food_type=food_type,
            is_active=_safe_bool(
                row.get("Active", True)
            ),
        )

        db.add(item)

        new_items[key] = item

        counters["items_created"] += 1

    await db.flush()

    items_map.update(new_items)

    # ------------------------------------------------------------------------
    # PHASE 2: PRICING
    # ------------------------------------------------------------------------

    pricings_map = await _load_existing_pricings(
        db,
        client_id,
    )

    for idx, row in pricing_df.iterrows():

        menu_item_name = _safe_str(
            row.get("Menu Item")
        )

        branch_code = _safe_str(
            row.get("Branch Code")
        ).upper()

        if not menu_item_name or not branch_code:
            continue

        branch = branches_map.get(
            branch_code
        )

        if branch is None:
            raise HTTPException(
                400,
                f"Branch '{branch_code}' not found.",
            )

        item = items_map.get(
            (
                menu_item_name.lower(),
                branch.id,
            )
        )

        if item is None:
            raise HTTPException(
                400,
                (
                    f"Menu Item '{menu_item_name}' "
                    f"not found for branch "
                    f"'{branch_code}'."
                ),
            )

        price = _safe_float(
            row.get("Price", 0),
            "Price",
        )

        cost_price = _safe_float(
            row.get("Cost Price", 0),
            "Cost Price",
        )

        discount = _safe_float(
            row.get("Discount", 0),
            "Discount",
        )

        tax = _safe_float(
            row.get("Tax", 0),
            "Tax",
        )

        cgst = _safe_float(
            row.get("CGST", 0),
            "CGST",
        )

        sgst = _safe_float(
            row.get("SGST", 0),
            "SGST",
        )

        calories_raw = row.get("Calories")

        calories = (
            int(calories_raw)
            if pd.notna(calories_raw)
            else None
        )

        is_active = _safe_bool(
            row.get("Active", True)
        )

        p_key = (
            item.id,
            branch.id,
        )

        existing = pricings_map.get(p_key)

        if existing:

            existing.price = price
            existing.cost_price = cost_price
            existing.discount = discount
            existing.tax = tax
            existing.cgst_rate = cgst
            existing.sgst_rate = sgst
            existing.calories = calories
            existing.is_active = is_active

            counters["pricing_updated"] += 1

        else:

            db.add(
                Pricing(
                    client_id=client_id,
                    item_id=item.id,
                    branch_id=branch.id,
                    price=price,
                    cost_price=cost_price,
                    discount=discount,
                    tax=tax,
                    cgst_rate=cgst,
                    sgst_rate=sgst,
                    calories=calories,
                    is_active=is_active,
                )
            )

            counters["pricing_created"] += 1

    await db.flush()

    # ------------------------------------------------------------------------
    # PHASE 3: BOM
    # ------------------------------------------------------------------------

    all_branch_ids = [
        b.id
        for b in branches_map.values()
    ]

    inventory_map = await _load_inventory_items(
        db,
        all_branch_ids,
    )

    godowns_map = await _load_godowns(
        db,
        all_branch_ids,
    )

    bom_map = await _load_existing_bom(db)

    for idx, row in bom_df.iterrows():

        menu_item_name = _safe_str(
            row.get("Menu Item")
        )

        inv_item_name = _safe_str(
            row.get("Inventory Item")
        )

        godown_name = _safe_str(
            row.get("Godown")
        )

        branch_code = _safe_str(
            row.get("Branch Code")
        ).upper()

        if (
            not menu_item_name
            or not inv_item_name
            or not godown_name
        ):
            continue

        branch = branches_map.get(
            branch_code
        )

        if branch is None:
            raise HTTPException(
                400,
                (
                    f"Branch Code "
                    f"'{branch_code}' not found."
                ),
            )

        item = items_map.get(
            (
                menu_item_name.lower(),
                branch.id,
            )
        )

        if item is None:
            raise HTTPException(
                400,
                (
                    f"Menu Item "
                    f"'{menu_item_name}' "
                    f"not found for Branch "
                    f"Code '{branch_code}'."
                ),
            )

        inv_item = inventory_map.get(
            (
                inv_item_name.lower(),
                branch.id,
            )
        )

        if inv_item is None:
            raise HTTPException(
                400,
                (
                    f"Inventory Item "
                    f"'{inv_item_name}' "
                    f"not found for branch "
                    f"'{branch_code}'. "
                    f"Please upload Inventory "
                    f"before importing BOM."
                ),
            )

        godown = await _find_or_create_godown(
            db=db,
            godown_name=godown_name,
            branch_id=branch.id,
            godowns_map=godowns_map,
            counters=counters,
        )

        try:
            quantity = float(
                row.get("Quantity")
            )
        except (
            TypeError,
            ValueError,
        ):
            raise HTTPException(
                400,
                (
                    f"Invalid quantity for "
                    f"BOM row {idx + 2}."
                ),
            )

        if quantity <= 0:
            raise HTTPException(
                400,
                (
                    f"Quantity must be positive "
                    f"(row {idx + 2})."
                ),
            )

        bom_key = (
            item.id,
            inv_item.id,
            godown.id,
        )

        existing_bom = bom_map.get(
            bom_key
        )

        if existing_bom:

            existing_bom.quantity_required = quantity

            counters["bom_updated"] += 1

        else:

            db.add(
                ItemIngredient(
                    item_id=item.id,
                    inventory_item_id=inv_item.id,
                    godown_id=godown.id,
                    quantity_required=quantity,
                )
            )

            counters["bom_created"] += 1

    return UploadResult(
        message="Menu uploaded successfully",
        counts=counters,
    )


# ============================================================================
# INVENTORY PROCESSOR
# ============================================================================

async def _process_inventory(
    db: AsyncSession,
    sheets: dict[str, pd.DataFrame],
    client_id: int,
) -> UploadResult:
    """
    Business logic for the inventory module.

    Supports:

    - Name
    - Branch Code
    - Godown
    - Category
    - Unit
    - Display Unit
    - Conversion Factor
    - Stock Qty
    - Reorder Level
    - Cost Per Unit
    - Vendor Name
    - Vendor Phone
    - Status

    Missing optional values receive safe defaults.

    Existing inventory items are UPDATED.
    New inventory items are CREATED.

    Missing Godowns are automatically CREATED.
    """

    inv_df = sheets["Inventory_Items"]

    # ------------------------------------------------------------------------
    # LOAD EXISTING DATA
    # ------------------------------------------------------------------------

    branches_map = await _load_branches(
        db,
        client_id,
    )

    all_branch_ids = [
        b.id
        for b in branches_map.values()
    ]

    godowns_map = await _load_godowns(
        db,
        all_branch_ids,
    )

    inventory_map = await _load_inventory_items(
        db,
        all_branch_ids,
    )

    # ------------------------------------------------------------------------
    # COUNTERS
    # ------------------------------------------------------------------------

    counters: dict[str, int] = {
        "godowns_created": 0,
        "godowns_skipped": 0,
        "items_created": 0,
        "items_updated": 0,
        "errors": 0,
    }

    # ------------------------------------------------------------------------
    # PROCESS ROWS
    # ------------------------------------------------------------------------

    for idx, row in inv_df.iterrows():

        excel_row = idx + 2

        # --------------------------------------------------------------------
        # BASIC FIELDS
        # --------------------------------------------------------------------

        name = _safe_str(
            row.get("Name")
        )

        branch_code = _safe_str(
            row.get("Branch Code")
        ).upper()

        unit = _safe_str(
            row.get("Unit")
        )

        # --------------------------------------------------------------------
        # REQUIRED VALIDATION
        # --------------------------------------------------------------------

        if not name:
            continue

        if not branch_code:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Row {excel_row}: "
                    f"'Branch Code' cannot be empty."
                ),
            )

        if not unit:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Row {excel_row}: "
                    f"'Unit' cannot be empty."
                ),
            )

        # --------------------------------------------------------------------
        # BRANCH
        # --------------------------------------------------------------------

        branch = branches_map.get(
            branch_code
        )

        if branch is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Row {excel_row}: "
                    f"Branch '{branch_code}' "
                    f"not found."
                ),
            )

        # --------------------------------------------------------------------
        # GODOWN
        # --------------------------------------------------------------------

        godown = None

        godown_name = _safe_str(
            row.get("Godown")
        )

        if godown_name:

            godown = await _find_or_create_godown(
                db=db,
                godown_name=godown_name,
                branch_id=branch.id,
                godowns_map=godowns_map,
                counters=counters,
            )

        # --------------------------------------------------------------------
        # CATEGORY
        # --------------------------------------------------------------------

        row_category = (
            _safe_str(
                row.get("Category")
            )
            or "other"
        )

        # --------------------------------------------------------------------
        # DISPLAY UNIT
        # --------------------------------------------------------------------

        display_unit = (
            _safe_str(
                row.get("Display Unit")
            )
            or "piece"
        )

        # --------------------------------------------------------------------
        # CONVERSION FACTOR
        # --------------------------------------------------------------------

        conversion_factor = _safe_float(
            row.get(
                "Conversion Factor",
                1.0,
            ),
            "Conversion Factor",
        )

        if conversion_factor <= 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Row {excel_row}: "
                    f"'Conversion Factor' "
                    f"must be positive."
                ),
            )

        # --------------------------------------------------------------------
        # STOCK QTY
        # --------------------------------------------------------------------

        stock_qty = _safe_float(
            row.get(
                "Stock Qty",
                0,
            ),
            "Stock Qty",
        )

        # --------------------------------------------------------------------
        # REORDER LEVEL
        # --------------------------------------------------------------------

        reorder_level = _safe_float(
            row.get(
                "Reorder Level",
                0,
            ),
            "Reorder Level",
        )

        # --------------------------------------------------------------------
        # COST PER UNIT
        # --------------------------------------------------------------------

        cost_per_unit = _safe_float(
            row.get(
                "Cost Per Unit",
                0,
            ),
            "Cost Per Unit",
        )

        # --------------------------------------------------------------------
        # VENDOR
        # --------------------------------------------------------------------

        vendor_name = (
            _safe_str(
                row.get("Vendor Name")
            )
            or None
        )

        vendor_phone = (
            _safe_str(
                row.get("Vendor Phone")
            )
            or None
        )

        # --------------------------------------------------------------------
        # STATUS
        # --------------------------------------------------------------------
        #
        # IMPORTANT FIX:
        #
        # OLD CODE:
        #
        #     if status_raw not in _VALID_STATUS:
        #
        # caused:
        #
        #     NameError:
        #     name '_VALID_STATUS' is not defined
        #
        # NOW status is normalized through _safe_inventory_status().
        # --------------------------------------------------------------------

        status_raw = _safe_inventory_status(
            row.get("Status"),
            excel_row,
        )

        # --------------------------------------------------------------------
        # INVENTORY LOOKUP
        # --------------------------------------------------------------------

        key = (
            name.lower(),
            branch.id,
        )

        existing = inventory_map.get(
            key
        )

        # --------------------------------------------------------------------
        # UPDATE EXISTING
        # --------------------------------------------------------------------

        if existing:

            existing.unit = unit

            existing.display_unit = (
                display_unit
            )

            existing.conversion_factor = (
                conversion_factor
            )

            existing.row_category = (
                row_category
            )

            existing.stock_qty = (
                stock_qty
            )

            existing.reorder_level = (
                reorder_level
            )

            existing.cost_per_unit = (
                cost_per_unit
            )

            existing.vendor_name = (
                vendor_name
            )

            existing.vendor_phone = (
                vendor_phone
            )

            existing.status = (
                status_raw
            )

            if godown is not None:
                existing.godown_id = (
                    godown.id
                )

            counters[
                "items_updated"
            ] += 1

        # --------------------------------------------------------------------
        # CREATE NEW
        # --------------------------------------------------------------------

        else:

            item = InventoryItem(
                name=name,
                branch_id=branch.id,
                godown_id=(
                    godown.id
                    if godown
                    else None
                ),
                unit=unit,
                display_unit=display_unit,
                conversion_factor=(
                    conversion_factor
                ),
                row_category=row_category,
                stock_qty=stock_qty,
                reorder_level=reorder_level,
                cost_per_unit=cost_per_unit,
                vendor_name=vendor_name,
                vendor_phone=vendor_phone,
                status=status_raw,
            )

            db.add(item)

            inventory_map[key] = item

            counters[
                "items_created"
            ] += 1

    # ------------------------------------------------------------------------
    # FLUSH
    # ------------------------------------------------------------------------

    await db.flush()

    # ------------------------------------------------------------------------
    # RESULT
    # ------------------------------------------------------------------------

    return UploadResult(
        message="Inventory uploaded successfully",
        counts=counters,
    )


# ============================================================================
# CATEGORY PROCESSOR
# ============================================================================

async def _process_category(
    db: AsyncSession,
    sheets: dict[str, pd.DataFrame],
    client_id: int,
) -> UploadResult:

    cat_df = sheets["Categories"]

    branches_map = await _load_branches(
        db,
        client_id,
    )

    categories_map = await _load_categories(
        db,
        client_id,
    )

    created = 0
    updated = 0

    for idx, row in cat_df.iterrows():

        excel_row = idx + 2

        name = _safe_str(
            row.get("Name")
        )

        branch_code = _safe_str(
            row.get("Branch Code")
        ).upper()

        if not name:
            continue

        if not branch_code:

            raise HTTPException(
                400,
                (
                    f"Row {excel_row}: "
                    f"'Branch Code' cannot be empty."
                ),
            )

        branch = branches_map.get(
            branch_code
        )

        if branch is None:

            raise HTTPException(
                400,
                (
                    f"Branch '{branch_code}' "
                    f"not found."
                ),
            )

        is_active = _safe_bool(
            row.get("Active", True)
        )

        key = (
            name.lower(),
            branch.id,
        )

        existing = categories_map.get(
            key
        )

        if existing:

            existing.is_active = is_active

            updated += 1

        else:

            category = Category(
                name=name,
                branch_id=branch.id,
                client_id=client_id,
                is_active=is_active,
            )

            db.add(category)

            categories_map[key] = category

            created += 1

    await db.flush()

    return UploadResult(
        message="Categories uploaded successfully",
        counts={
            "categories_created": created,
            "categories_updated": updated,
        },
    )


# ============================================================================
# PATCH HANDLERS
# ============================================================================

UPLOAD_CONFIG["menu"].handler = _process_menu

UPLOAD_CONFIG["inventory"].handler = (
    _process_inventory
)

UPLOAD_CONFIG["category"].handler = (
    _process_category
)


# ============================================================================
# BULK UPLOAD SERVICE
# ============================================================================

class BulkUploadService:
    """
    Dispatcher + orchestrator for all bulk-upload modules.
    """

    @staticmethod
    async def upload(
        db: AsyncSession,
        file: UploadFile,
        module: str,
        client_id: int,
    ) -> dict:

        module = module.lower().strip()

        config = UPLOAD_CONFIG.get(
            module
        )

        if config is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown module '{module}'. "
                    f"Supported: "
                    f"{list(UPLOAD_CONFIG)}"
                ),
            )

        # --------------------------------------------------------------------
        # READ FILE
        # --------------------------------------------------------------------

        raw_bytes = await file.read()

        if not raw_bytes:

            raise HTTPException(
                status_code=400,
                detail="Uploaded Excel file is empty.",
            )

        # --------------------------------------------------------------------
        # PARSE EXCEL
        # --------------------------------------------------------------------

        try:

            xls = pd.ExcelFile(
                io.BytesIO(raw_bytes)
            )

        except Exception as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not parse uploaded "
                    f"file as Excel: {exc}"
                ),
            )

        # --------------------------------------------------------------------
        # READ REQUIRED SHEETS
        # --------------------------------------------------------------------

        sheets: dict[
            str,
            pd.DataFrame,
        ] = {}

        for sheet_cfg in config.sheets:

            if (
                sheet_cfg.name
                not in xls.sheet_names
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Sheet '{sheet_cfg.name}' "
                        f"is missing from the "
                        f"uploaded file."
                    ),
                )

            df = (
                xls
                .parse(sheet_cfg.name)
                .dropna(how="all")
            )

            # Normalize column names
            df.columns = [
                str(col).strip()
                for col in df.columns
            ]

            missing_cols = [
                c
                for c in sheet_cfg.required_columns
                if c not in df.columns
            ]

            if missing_cols:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Column(s) "
                        f"{missing_cols} "
                        f"missing in sheet "
                        f"'{sheet_cfg.name}'."
                    ),
                )

            sheets[
                sheet_cfg.name
            ] = df

        # --------------------------------------------------------------------
        # PROCESS UPLOAD
        # --------------------------------------------------------------------

        try:

            if config.handler is None:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"No upload handler "
                        f"configured for "
                        f"module '{module}'."
                    ),
                )

            result: UploadResult = (
                await config.handler(
                    db,
                    sheets,
                    client_id,
                )
            )

            await db.commit()

        except HTTPException:

            await db.rollback()

            raise

        except Exception as exc:

            await db.rollback()

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Unexpected error during "
                    f"'{module}' upload: {exc}"
                ),
            ) from exc

        return result.to_dict()

    # ------------------------------------------------------------------------
    # DOWNLOAD TEMPLATE
    # ------------------------------------------------------------------------

    @staticmethod
    async def download_template(
        module: str,
    ) -> FileResponse:

        module = module.lower().strip()

        if module not in TEMPLATES:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"No template found for "
                    f"module '{module}'. "
                    f"Available: "
                    f"{list(TEMPLATES)}"
                ),
            )

        temp_dir = Path("temp")

        temp_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path = (
            temp_dir
            / f"{module}_template.xlsx"
        )

        with pd.ExcelWriter(
            file_path,
            engine="openpyxl",
        ) as writer:

            for (
                sheet_name,
                sample_data,
            ) in TEMPLATES[module].items():

                df = pd.DataFrame(
                    sample_data
                )

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False,
                )

                _auto_width_excel(
                    writer,
                    sheet_name,
                )

        return FileResponse(
            path=str(file_path),
            filename=(
                f"{module}_template.xlsx"
            ),
            media_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )


# ============================================================================
# BRANCH PERMISSION HELPER
# ============================================================================

async def get_allowed_branches(
    db: AsyncSession,
    client: Any,
) -> list[Branch]:
    """
    Determine which branches the authenticated
    client may access.
    """

    # ------------------------------------------------------------------------
    # ALL BRANCHES
    # ------------------------------------------------------------------------

    if getattr(
        client,
        "all_branches",
        False,
    ):

        result = await db.execute(
            select(Branch).where(
                Branch.client_id
                == client.id
            )
        )

        branches = (
            result
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------------
    # ASSIGNED BRANCHES
    # ------------------------------------------------------------------------

    else:

        assigned_ids: list[int] = (
            getattr(
                client,
                "branch_ids",
                [],
            )
            or []
        )

        if not assigned_ids:

            raise HTTPException(
                status_code=403,
                detail=(
                    "No branches are assigned "
                    "to your account."
                ),
            )

        result = await db.execute(
            select(Branch).where(
                Branch.client_id
                == client.id,
                Branch.id.in_(
                    assigned_ids
                ),
            )
        )

        branches = (
            result
            .scalars()
            .all()
        )

    if not branches:

        raise HTTPException(
            status_code=403,
            detail=(
                "No accessible branches "
                "found for your account."
            ),
        )

    return list(branches)


# ============================================================================
# GENERIC EXCEL RESPONSE
# ============================================================================

def _build_excel_response(
    sheets: dict[str, pd.DataFrame],
    filename: str,
) -> FileResponse:

    if not sheets:

        raise HTTPException(
            status_code=404,
            detail="No data available for export.",
        )

    temp_dir = Path("temp")

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = (
        temp_dir
        / filename
    )

    try:

        with pd.ExcelWriter(
            file_path,
            engine="openpyxl",
        ) as writer:

            for (
                sheet_name,
                df,
            ) in sheets.items():

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False,
                )

                _auto_width_excel(
                    writer,
                    sheet_name,
                )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to generate "
                f"Excel file: {exc}"
            ),
        ) from exc

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )


# ============================================================================
# EXPORT - BILL
# ============================================================================

async def _export_bill(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:

    result = await db.execute(
        select(Bill, Branch)
        .join(
            Branch,
            Bill.branch_id == Branch.id,
        )
        .where(
            Bill.branch_id.in_(branch_ids)
        )
    )

    rows = result.all()

    data = [
        {
            "Invoice No": bill.invoice_no,
            "Branch Code": branch.branch_code,
            "Order Type": bill.order_type,
            "Customer Name": (
                bill.customer_name or ""
            ),
            "Customer Phone": (
                bill.customer_phone or ""
            ),
            "Payment Status": (
                bill.payment_status.value
                if bill.payment_status
                else ""
            ),
            "Payment Method": (
                bill.payment_method or ""
            ),
            "Subtotal": bill.subtotal,
            "CGST %": bill.cgst_percent,
            "CGST Amount": bill.cgst_amount,
            "SGST %": bill.sgst_percent,
            "SGST Amount": bill.sgst_amount,
            "Service Charge %": (
                bill.service_charge_percent
            ),
            "Service Charge Amount": (
                bill.service_charge_amount
            ),
            "Tax Total": bill.tax_total,
            "Discount Amount": (
                bill.discount_amount
            ),
            "Round Off Amount": (
                bill.round_off_amount
            ),
            "Grand Total": bill.grand_total,
            "Paid Amount": bill.paid_amount,
            "Due Amount": bill.due_amount,
            "Offer Discount": (
                bill.offer_discount
            ),
            "Final Amount": bill.final_amount,
            "Notes": bill.notes or "",
            "Footer Message": (
                bill.footer_message or ""
            ),
            "Billed At": (
                bill.billed_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if bill.billed_at
                else ""
            ),
        }
        for bill, branch in rows
    ]

    return {
        "Bills": pd.DataFrame(data)
    }


# ============================================================================
# EXPORT - MENU
# ============================================================================

async def _export_menu(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:

    # ------------------------------------------------------------------------
    # MENU ITEMS
    # ------------------------------------------------------------------------

    items_result = await db.execute(
        select(
            Item,
            Branch,
            Category,
        )
        .join(
            Branch,
            Item.branch_id == Branch.id,
        )
        .join(
            Category,
            Item.category_id == Category.id,
        )
        .where(
            Item.branch_id.in_(branch_ids)
        )
    )

    items_rows = items_result.all()

    menu_items_data = [
        {
            "Name": item.name,
            "Category": category.name,
            "Branch Code": branch.branch_code,
            "Food Type": (
                item.food_type.value
                if item.food_type
                else ""
            ),
            "Active": item.is_active,
        }
        for item, branch, category
        in items_rows
    ]

    # ------------------------------------------------------------------------
    # PRICING
    # ------------------------------------------------------------------------

    pricing_result = await db.execute(
        select(
            Pricing,
            Item,
            Branch,
        )
        .join(
            Item,
            Pricing.item_id == Item.id,
        )
        .join(
            Branch,
            Pricing.branch_id == Branch.id,
        )
        .where(
            Pricing.branch_id.in_(branch_ids)
        )
    )

    pricing_rows = pricing_result.all()

    pricing_data = [
        {
            "Menu Item": item.name,
            "Branch Code": branch.branch_code,
            "Price": pricing.price,
            "Cost Price": pricing.cost_price,
            "Discount": pricing.discount,
            "Tax": pricing.tax,
            "CGST": pricing.cgst_rate,
            "SGST": pricing.sgst_rate,
            "Calories": pricing.calories,
            "Active": pricing.is_active,
        }
        for pricing, item, branch
        in pricing_rows
    ]

    # ------------------------------------------------------------------------
    # BOM
    # ------------------------------------------------------------------------

    bom_result = await db.execute(
        select(
            ItemIngredient,
            Item,
            InventoryItem,
            Godown,
            Branch,
        )
        .join(
            Item,
            ItemIngredient.item_id
            == Item.id,
        )
        .join(
            InventoryItem,
            ItemIngredient.inventory_item_id
            == InventoryItem.id,
        )
        .join(
            Godown,
            ItemIngredient.godown_id
            == Godown.id,
        )
        .join(
            Branch,
            Item.branch_id == Branch.id,
        )
        .where(
            Item.branch_id.in_(branch_ids)
        )
    )

    bom_rows = bom_result.all()

    bom_data = [
        {
            "Menu Item": item.name,
            "Branch Code": branch.branch_code,
            "Inventory Item": inv_item.name,
            "Godown": godown.name,
            "Quantity": (
                ingredient.quantity_required
            ),
        }
        for (
            ingredient,
            item,
            inv_item,
            godown,
            branch,
        ) in bom_rows
    ]

    return {
        "Menu_Items": pd.DataFrame(
            menu_items_data
        ),
        "Pricing": pd.DataFrame(
            pricing_data
        ),
        "BOM": pd.DataFrame(
            bom_data
        ),
    }


# ============================================================================
# EXPORT - INVENTORY
# ============================================================================

async def _export_inventory(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:

    result = await db.execute(
        select(
            InventoryItem,
            Branch,
            Godown,
        )
        .join(
            Branch,
            InventoryItem.branch_id
            == Branch.id,
        )
        .outerjoin(
            Godown,
            InventoryItem.godown_id
            == Godown.id,
        )
        .where(
            InventoryItem.branch_id.in_(
                branch_ids
            )
        )
    )

    rows = result.all()

    data = [
        {
            "Name": inv.name,
            "Branch Code": branch.branch_code,
            "Godown": (
                godown.name
                if godown
                else ""
            ),
            "Category": inv.row_category,
            "Unit": inv.unit,
            "Display Unit": inv.display_unit,
            "Conversion Factor": (
                inv.conversion_factor
            ),
            "Stock Qty": inv.stock_qty,
            "Reorder Level": (
                inv.reorder_level
            ),
            "Cost Per Unit": (
                inv.cost_per_unit
            ),
            "Vendor Name": (
                inv.vendor_name or ""
            ),
            "Vendor Phone": (
                inv.vendor_phone or ""
            ),
            "Status": (
                inv.status.value
                if hasattr(
                    inv.status,
                    "value",
                )
                else inv.status
            ),
        }
        for inv, branch, godown
        in rows
    ]

    return {
        "Inventory_Items": pd.DataFrame(data)
    }


# ============================================================================
# EXPORT - CATEGORY
# ============================================================================

async def _export_category(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:

    result = await db.execute(
        select(
            Category,
            Branch,
        )
        .join(
            Branch,
            Category.branch_id
            == Branch.id,
        )
        .where(
            Category.branch_id.in_(
                branch_ids
            )
        )
    )

    rows = result.all()

    data = [
        {
            "Name": category.name,
            "Branch Code": branch.branch_code,
            "Active": category.is_active,
        }
        for category, branch
        in rows
    ]

    return {
        "Categories": pd.DataFrame(data)
    }


# ============================================================================
# EXPORT - ALL REPORTS
# ============================================================================

async def _export_all_reports(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:

    from datetime import datetime, timedelta
    from sqlalchemy import func

    # ------------------------------------------------------------------------
    # BILLS
    # ------------------------------------------------------------------------

    bills_result = await db.execute(
        select(
            Bill,
            Branch,
        )
        .join(
            Branch,
            Bill.branch_id == Branch.id,
        )
        .where(
            Bill.branch_id.in_(branch_ids)
        )
    )

    bills_rows = bills_result.all()

    bills_data = [
        {
            "Invoice No": bill.invoice_no,
            "Branch Code": branch.branch_code,
            "Order Type": bill.order_type,
            "Customer Name": (
                bill.customer_name or ""
            ),
            "Customer Phone": (
                bill.customer_phone or ""
            ),
            "Payment Status": (
                bill.payment_status.value
                if bill.payment_status
                else ""
            ),
            "Payment Method": (
                bill.payment_method or ""
            ),
            "Subtotal": bill.subtotal,
            "CGST %": bill.cgst_percent,
            "CGST Amount": bill.cgst_amount,
            "SGST %": bill.sgst_percent,
            "SGST Amount": bill.sgst_amount,
            "Service Charge %": (
                bill.service_charge_percent
            ),
            "Service Charge Amount": (
                bill.service_charge_amount
            ),
            "Tax Total": bill.tax_total,
            "Discount Amount": (
                bill.discount_amount
            ),
            "Round Off Amount": (
                bill.round_off_amount
            ),
            "Grand Total": bill.grand_total,
            "Paid Amount": bill.paid_amount,
            "Due Amount": bill.due_amount,
            "Offer Discount": (
                bill.offer_discount
            ),
            "Final Amount": bill.final_amount,
            "Notes": bill.notes or "",
            "Billed At": (
                bill.billed_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if bill.billed_at
                else ""
            ),
        }
        for bill, branch
        in bills_rows
    ]

    # ------------------------------------------------------------------------
    # FINANCIAL SUMMARY
    # ------------------------------------------------------------------------

    financial_data = []

    for bid in branch_ids:

        branch_obj = next(
            (
                branch
                for bill, branch
                in bills_rows
                if bill.branch_id == bid
            ),
            None,
        )

        branch_code = (
            branch_obj.branch_code
            if branch_obj
            else str(bid)
        )

        revenue = await db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        Bill.grand_total
                    ),
                    0,
                )
            )
            .where(
                Bill.branch_id == bid,
                Bill.payment_status
                == PaymentStatus.complete,
            )
        ) or 0

        paid_orders = await db.scalar(
            select(
                func.count(Bill.id)
            )
            .where(
                Bill.branch_id == bid,
                Bill.payment_status
                == PaymentStatus.complete,
            )
        ) or 0

        tax_total = await db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        Bill.tax_total
                        + Bill.service_charge_amount
                    ),
                    0,
                )
            )
            .where(
                Bill.branch_id == bid,
                Bill.payment_status
                == PaymentStatus.complete,
            )
        ) or 0

        financial_data.append(
            {
                "Branch Code": branch_code,
                "Total Revenue": round(
                    float(revenue),
                    2,
                ),
                "Paid Orders": paid_orders,
                "Tax Collected": round(
                    float(tax_total),
                    2,
                ),
                "Avg Order Value": (
                    round(
                        float(revenue)
                        / paid_orders,
                        2,
                    )
                    if paid_orders
                    else 0
                ),
            }
        )

    # ------------------------------------------------------------------------
    # SALES SUMMARY
    # ------------------------------------------------------------------------

    today = datetime.utcnow()

    start_of_week = (
        today
        - timedelta(
            days=today.weekday()
        )
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_of_week = (
        start_of_week
        + timedelta(days=6)
    ).replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=999999,
    )

    sales_data = []

    for bid in branch_ids:

        branch_obj = next(
            (
                branch
                for bill, branch
                in bills_rows
                if bill.branch_id == bid
            ),
            None,
        )

        branch_code = (
            branch_obj.branch_code
            if branch_obj
            else str(bid)
        )

        week_orders = await db.scalar(
            select(
                func.count(Order.id)
            )
            .where(
                Order.branch_id == bid,
                Order.created_at
                >= start_of_week,
                Order.created_at
                <= end_of_week,
            )
        ) or 0

        week_revenue = await db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        Bill.grand_total
                    ),
                    0,
                )
            )
            .where(
                Bill.branch_id == bid,
                Bill.created_at
                >= start_of_week,
                Bill.created_at
                <= end_of_week,
                Bill.payment_status
                == PaymentStatus.complete,
            )
        ) or 0

        sales_data.append(
            {
                "Branch Code": branch_code,
                "This Week Orders": week_orders,
                "This Week Revenue": round(
                    float(week_revenue),
                    2,
                ),
                "Avg Daily Orders": round(
                    week_orders / 7,
                    1,
                ),
            }
        )

    # ------------------------------------------------------------------------
    # TOP SELLING ITEMS
    # ------------------------------------------------------------------------

    top_items_result = await db.execute(
        select(
            Item.name.label(
                "item_name"
            ),
            func.sum(
                OrderItem.quantity
            ).label(
                "quantity_sold"
            ),
        )
        .join(
            OrderItem,
            OrderItem.item_id
            == Item.id,
        )
        .join(
            Order,
            Order.id
            == OrderItem.order_id,
        )
        .join(
            Bill,
            Bill.order_id
            == Order.id,
        )
        .where(
            Order.branch_id.in_(
                branch_ids
            ),
            Bill.payment_status
            == PaymentStatus.complete,
        )
        .group_by(
            Item.name
        )
        .order_by(
            func.sum(
                OrderItem.quantity
            ).desc()
        )
        .limit(50)
    )

    top_items_rows = (
        top_items_result.all()
    )

    total_qty = sum(
        r.quantity_sold
        for r in top_items_rows
    )

    top_items_data = [
        {
            "Item Name": r.item_name,
            "Quantity Sold": r.quantity_sold,
            "% of Total": (
                round(
                    (
                        r.quantity_sold
                        / total_qty
                    )
                    * 100,
                    2,
                )
                if total_qty
                else 0
            ),
        }
        for r in top_items_rows
    ]

    # ------------------------------------------------------------------------
    # CATEGORY DISTRIBUTION
    # ------------------------------------------------------------------------

    cat_result = await db.execute(
        select(
            Category.name.label(
                "category_name"
            ),
            Branch.branch_code,
            func.count(
                Item.id
            ).label(
                "item_count"
            ),
        )
        .outerjoin(
            Item,
            Item.category_id
            == Category.id,
        )
        .join(
            Branch,
            Category.branch_id
            == Branch.id,
        )
        .where(
            Category.branch_id.in_(
                branch_ids
            )
        )
        .group_by(
            Category.name,
            Branch.branch_code,
        )
        .order_by(
            func.count(
                Item.id
            ).desc()
        )
    )

    cat_rows = cat_result.all()

    total_cat_items = sum(
        r.item_count
        for r in cat_rows
    )

    category_data = [
        {
            "Branch Code": r.branch_code,
            "Category": r.category_name,
            "Item Count": r.item_count,
            "% of Menu": (
                round(
                    (
                        r.item_count
                        / total_cat_items
                    )
                    * 100,
                    2,
                )
                if total_cat_items
                else 0
            ),
        }
        for r in cat_rows
    ]

    # ------------------------------------------------------------------------
    # INVENTORY SUMMARY
    # ------------------------------------------------------------------------

    inv_result = await db.execute(
        select(
            InventoryItem,
            Branch,
            Godown,
        )
        .join(
            Branch,
            InventoryItem.branch_id
            == Branch.id,
        )
        .outerjoin(
            Godown,
            InventoryItem.godown_id
            == Godown.id,
        )
        .where(
            InventoryItem.branch_id.in_(
                branch_ids
            )
        )
    )

    inv_rows = inv_result.all()

    inventory_data = [
        {
            "Branch Code": branch.branch_code,
            "Name": inv.name,
            "Category": inv.row_category,
            "Godown": (
                godown.name
                if godown
                else ""
            ),
            "Unit": inv.unit,
            "Stock Qty": inv.stock_qty,
            "Reorder Level": (
                inv.reorder_level
            ),
            "Cost Per Unit": (
                inv.cost_per_unit
            ),
            "Stock Value": round(
                (
                    inv.stock_qty or 0
                )
                * (
                    inv.cost_per_unit or 0
                ),
                2,
            ),
            "Status": (
                inv.status.value
                if hasattr(
                    inv.status,
                    "value",
                )
                else inv.status
            ),
            "Vendor Name": (
                inv.vendor_name or ""
            ),
            "Vendor Phone": (
                inv.vendor_phone or ""
            ),
        }
        for inv, branch, godown
        in inv_rows
    ]

    # ------------------------------------------------------------------------
    # PAYMENT METHOD TOTALS
    # ------------------------------------------------------------------------

    payments_result = await db.execute(
        select(
            Payment,
            Branch,
        )
        .join(
            Branch,
            Payment.branch_id
            == Branch.id,
        )
        .where(
            Branch.id.in_(branch_ids)
        )
    )

    payments_rows = (
        payments_result.all()
    )

    payment_totals: dict[
        str,
        dict,
    ] = {}

    for payment, branch in payments_rows:

        code = branch.branch_code

        if code not in payment_totals:

            payment_totals[code] = {
                "Branch Code": code,
                "Cash Orders": 0,
                "Cash Total": 0,
                "UPI Orders": 0,
                "UPI Total": 0,
                "Card Orders": 0,
                "Card Total": 0,
                "Credit Orders": 0,
                "Credit Total": 0,
                "Grand Total": 0,
            }

        breakdown = (
            payment.payment_breakdown
            or []
        )

        for item in breakdown:

            method = (
                item.get(
                    "payment_method"
                )
                or ""
            ).lower()

            amount = float(
                item.get(
                    "payment_amount",
                    0,
                )
                or 0
            )

            if method == "cash":

                payment_totals[code][
                    "Cash Orders"
                ] += 1

                payment_totals[code][
                    "Cash Total"
                ] += amount

            elif method == "upi":

                payment_totals[code][
                    "UPI Orders"
                ] += 1

                payment_totals[code][
                    "UPI Total"
                ] += amount

            elif method == "card":

                payment_totals[code][
                    "Card Orders"
                ] += 1

                payment_totals[code][
                    "Card Total"
                ] += amount

            elif method == "credit":

                payment_totals[code][
                    "Credit Orders"
                ] += 1

                payment_totals[code][
                    "Credit Total"
                ] += amount

    for row in payment_totals.values():

        row["Grand Total"] = round(
            row["Cash Total"]
            + row["UPI Total"]
            + row["Card Total"]
            + row["Credit Total"],
            2,
        )

        for key in (
            "Cash Total",
            "UPI Total",
            "Card Total",
            "Credit Total",
        ):

            row[key] = round(
                row[key],
                2,
            )

    payment_data = list(
        payment_totals.values()
    )

    # ------------------------------------------------------------------------
    # RETURN ALL REPORTS
    # ------------------------------------------------------------------------

    return {
        "Bills": pd.DataFrame(
            bills_data
        ),
        "Financial_Summary": pd.DataFrame(
            financial_data
        ),
        "Sales_Summary": pd.DataFrame(
            sales_data
        ),
        "Top_Selling_Items": pd.DataFrame(
            top_items_data
        ),
        "Category_Distribution": pd.DataFrame(
            category_data
        ),
        "Inventory": pd.DataFrame(
            inventory_data
        ),
        "Payment_Totals": pd.DataFrame(
            payment_data
        ),
    }


# ============================================================================
# EXPORT HANDLER REGISTRY
# ============================================================================

ExportHandler = Callable


EXPORT_HANDLERS: dict[
    str,
    ExportHandler,
] = {
    "menu": _export_menu,
    "inventory": _export_inventory,
    "category": _export_category,
    "bill": _export_bill,
    "all_reports": _export_all_reports,
}


# ============================================================================
# BULK EXPORT SERVICE
# ============================================================================

class BulkExportService:
    """
    Generic export orchestrator.
    """

    @staticmethod
    async def export(
        db: AsyncSession,
        module: str,
        client: Any,
    ) -> FileResponse:

        module = module.lower().strip()

        handler = EXPORT_HANDLERS.get(
            module
        )

        if handler is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown export module "
                    f"'{module}'. Supported: "
                    f"{list(EXPORT_HANDLERS)}"
                ),
            )

        allowed_branches = (
            await get_allowed_branches(
                db,
                client,
            )
        )

        branch_ids = [
            b.id
            for b in allowed_branches
        ]

        try:

            sheets = await handler(
                db,
                branch_ids,
                client.id,
            )

        except HTTPException:
            raise

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Unexpected error during "
                    f"'{module}' export: {exc}"
                ),
            ) from exc

        total_rows = sum(
            len(df)
            for df in sheets.values()
        )

        if total_rows == 0:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"No data found for "
                    f"module '{module}' in your "
                    f"accessible branches."
                ),
            )

        from datetime import date

        filename = (
            f"{module}_export_"
            f"{date.today()}.xlsx"
        )

        return _build_excel_response(
            sheets,
            filename,
        )