"""
app/accounts/uploads/service.py
Generic Bulk Upload Framework — Production Ready
"""

from __future__ import annotations
from app.accounts.order.model import Order, OrderItem
from app.accounts.payment.model import Payment
from app.accounts.bill.enum import PaymentStatus
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from app.accounts.bill.model import Bill
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.item.model import Item
from app.accounts.ingredient.model import ItemIngredient
from app.accounts.inventory.model import Godown, InventoryItem
from app.accounts.category.model import Category
from app.accounts.pricing.model import Pricing
from app.accounts.branch.model import Branch


# ---------------------------------------------------------------------------
# Template & Config Definitions
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, list[dict]]] = {
    "menu": {
        "Menu_Items": [
            {
                "Name": "Veg Burger",
                "Category": "Fast Food",
                "Branch Code": "BR001",
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
        ],
    },
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
    "category": {
        "Categories": [
            {
                "Name": "Fast Food",
                "Branch Code": "BR001",
                "Active": True,
            }
        ]
    },
}


@dataclass
class SheetConfig:
    """Describes a single sheet within a module's upload file."""
    name: str
    required_columns: list[str]


@dataclass
class ModuleConfig:
    """
    Full configuration for one uploadable module.

    sheets   — ordered list of SheetConfig; all must be present in the file.
    handler  — async callable that owns the module's business logic.
               Signature: handler(db, sheets, client_id) -> UploadResult
    """
    sheets: list[SheetConfig]
    handler: Callable


UPLOAD_CONFIG: dict[str, ModuleConfig] = {
    "menu": ModuleConfig(
        sheets=[
            SheetConfig("Menu_Items", ["Name", "Category", "Branch Code", "Active"]),
            SheetConfig(
                "Pricing",
                ["Menu Item", "Branch Code", "Price", "Cost Price",
                 "Discount", "Tax", "CGST", "SGST", "Calories", "Active"],
            ),
            SheetConfig("BOM", ["Menu Item", "Branch Code", "Inventory Item", "Godown", "Quantity"]),
        ],
        handler=None,  # patched below
    ),
    "inventory": ModuleConfig(
        sheets=[
            SheetConfig(
                "Inventory_Items",
                ["Name", "Branch Code", "Unit"],
            )
        ],
        handler=None,  # patched below
    ),
    "category": ModuleConfig(
        sheets=[
            SheetConfig("Categories", ["Name", "Branch Code", "Active"])
        ],
        handler=None,  # patched below
    ),
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class UploadResult:
    message: str = "Upload successful"
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"message": self.message, **self.counts}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _safe_str(val: Any) -> str:
    return str(val).strip() if pd.notna(val) else ""


def _safe_float(val: Any, field_name: str) -> float:
    try:
        result = float(val)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid numeric value for '{field_name}': {val!r}",
        )
    if result < 0:
        raise HTTPException(
            status_code=400,
            detail=f"'{field_name}' cannot be negative. Got {result}.",
        )
    return result


def _safe_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


def _auto_width_excel(writer: pd.ExcelWriter, sheet_name: str) -> None:
    ws = writer.sheets[sheet_name]
    for col in ws.columns:
        max_len = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in col
        )
        ws.column_dimensions[col[0].column_letter].width = max_len + 5


# ---------------------------------------------------------------------------
# Shared DB loaders
# ---------------------------------------------------------------------------

async def _load_branches(db: AsyncSession, client_id: int) -> dict[str, Branch]:
    result = await db.execute(select(Branch).where(Branch.client_id == client_id))
    return {b.branch_code.strip().upper(): b for b in result.scalars().all()}


async def _load_categories(db: AsyncSession, client_id: int) -> dict[tuple[str, int], Category]:
    result = await db.execute(select(Category).where(Category.client_id == client_id))
    return {(c.name.strip().lower(), c.branch_id): c for c in result.scalars().all()}


async def _load_existing_items(db: AsyncSession, client_id: int) -> dict[tuple[str, int], Item]:
    result = await db.execute(select(Item).where(Item.client_id == client_id))
    return {(i.name.strip().lower(), i.branch_id): i for i in result.scalars().all()}


async def _load_inventory_items(db: AsyncSession, branch_ids: list[int]) -> dict[tuple[str, int], InventoryItem]:
    result = await db.execute(select(InventoryItem).where(InventoryItem.branch_id.in_(branch_ids)))
    return {(iv.name.strip().lower(), iv.branch_id): iv for iv in result.scalars().all()}


async def _load_godowns(db: AsyncSession, branch_ids: list[int]) -> dict[tuple[str, int], Godown]:
    result = await db.execute(select(Godown).where(Godown.branch_id.in_(branch_ids)))
    return {(g.name.strip().lower(), g.branch_id): g for g in result.scalars().all()}


async def _load_existing_pricings(db: AsyncSession, client_id: int) -> dict[tuple[int, int], Pricing]:
    result = await db.execute(select(Pricing).where(Pricing.client_id == client_id))
    return {(p.item_id, p.branch_id): p for p in result.scalars().all()}


async def _load_existing_bom(db: AsyncSession) -> dict[tuple[int, int, int], ItemIngredient]:
    result = await db.execute(select(ItemIngredient))
    return {(bi.item_id, bi.inventory_item_id, bi.godown_id): bi for bi in result.scalars().all()}


# ---------------------------------------------------------------------------
# Auto-create helpers (idempotent: check map first, never duplicate)
# ---------------------------------------------------------------------------

async def _find_or_create_godown(
    db: AsyncSession,
    godown_name: str,
    branch_id: int,
    godowns_map: dict[tuple[str, int], Godown],
    counters: dict[str, int],
) -> Godown:
    """
    Return an existing Godown (case-insensitive name + branch_id match)
    or create a new one with sensible defaults.
    Always flushes after creation and updates godowns_map in-place.
    """
    key = (godown_name.strip().lower(), branch_id)
    godown = godowns_map.get(key)
    if godown is not None:
        counters["godowns_skipped"] = counters.get("godowns_skipped", 0) + 1
        return godown

    # Not in map — create it.
    godown = Godown(
        name=godown_name.strip(),
        branch_id=branch_id,
    )
    db.add(godown)
    await db.flush()  # populate godown.id immediately
    godowns_map[key] = godown
    counters["godowns_created"] = counters.get("godowns_created", 0) + 1
    return godown


async def _find_or_create_category(
    db: AsyncSession,
    category_name: str,
    branch_id: int,
    client_id: int,
    categories_map: dict[tuple[str, int], Category],
    counters: dict[str, int],
) -> Category:
    """
    Return an existing Category (case-insensitive name + branch_id match)
    or create a new one.
    Always flushes after creation and updates categories_map in-place.
    """
    key = (category_name.strip().lower(), branch_id)
    category = categories_map.get(key)
    if category is not None:
        counters["categories_skipped"] = counters.get("categories_skipped", 0) + 1
        return category

    # Not in map — create it.
    category = Category(
        name=category_name.strip(),
        branch_id=branch_id,
        client_id=client_id,
    )
    db.add(category)
    await db.flush()  # populate category.id immediately
    categories_map[key] = category
    counters["categories_created"] = counters.get("categories_created", 0) + 1
    return category


# ---------------------------------------------------------------------------
# Module-specific processors
# ---------------------------------------------------------------------------

async def _process_menu(
    db: AsyncSession,
    sheets: dict[str, pd.DataFrame],
    client_id: int,
) -> UploadResult:
    """Business logic for the 'menu' module. Handles Menu Items -> Pricing -> BOM.

    Auto-creates missing Categories and Godowns (case-insensitive dedup).
    Inventory Items are NOT auto-created — they must exist in the DB.
    """
    menu_df = sheets["Menu_Items"]
    pricing_df = sheets["Pricing"]
    bom_df = sheets["BOM"]

    branches_map = await _load_branches(db, client_id)
    categories_map = await _load_categories(db, client_id)
    items_map = await _load_existing_items(db, client_id)

    # Shared counters dict — helpers mutate this in-place.
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
    new_items: dict[tuple[str, int], Item] = {}

    # ----------------------------------------------------------------
    # Phase 1: Menu Items  (auto-create Category if missing)
    # ----------------------------------------------------------------
    for idx, row in menu_df.iterrows():
        name = _safe_str(row.get("Name"))
        branch_code = _safe_str(row.get("Branch Code")).upper()
        category_name = _safe_str(row.get("Category"))

        if not name:
            continue
        if not branch_code:
            raise HTTPException(400, f"Row {idx + 2}: 'Branch Code' cannot be empty.")
        if not category_name:
            raise HTTPException(400, f"Row {idx + 2}: 'Category' cannot be empty.")

        branch = branches_map.get(branch_code)
        if branch is None:
            raise HTTPException(400, f"Branch '{branch_code}' not found.")

        # Auto-create category if it does not exist.
        category = await _find_or_create_category(
            db=db,
            category_name=category_name,
            branch_id=branch.id,
            client_id=client_id,
            categories_map=categories_map,
            counters=counters,
        )

        key = (name.lower(), branch.id)
        if key in items_map or key in new_items:
            # Item already exists — treat as update (we update in-place later if needed)
            counters["items_updated"] += 1
            continue

        item = Item(
            name=name,
            category_id=category.id,
            branch_id=branch.id,
            client_id=client_id,
            is_active=_safe_bool(row.get("Active", True)),
        )
        db.add(item)
        new_items[key] = item
        counters["items_created"] += 1

    await db.flush()
    items_map.update(new_items)

    # ----------------------------------------------------------------
    # Phase 2: Pricing  (create or update)
    # ----------------------------------------------------------------
    pricings_map = await _load_existing_pricings(db, client_id)

    for idx, row in pricing_df.iterrows():
        menu_item_name = _safe_str(row.get("Menu Item"))
        branch_code = _safe_str(row.get("Branch Code")).upper()

        if not menu_item_name or not branch_code:
            continue

        branch = branches_map.get(branch_code)
        if branch is None:
            raise HTTPException(400, f"Branch '{branch_code}' not found.")

        item = items_map.get((menu_item_name.lower(), branch.id))
        if item is None:
            raise HTTPException(
                400,
                f"Menu Item '{menu_item_name}' not found for branch '{branch_code}'.",
            )

        price = _safe_float(row.get("Price", 0), "Price")
        cost_price = _safe_float(row.get("Cost Price", 0), "Cost Price")
        discount = _safe_float(row.get("Discount", 0), "Discount")
        tax = _safe_float(row.get("Tax", 0), "Tax")
        cgst = _safe_float(row.get("CGST", 0), "CGST")
        sgst = _safe_float(row.get("SGST", 0), "SGST")
        calories_raw = row.get("Calories")
        calories = int(calories_raw) if pd.notna(calories_raw) else None
        is_active = _safe_bool(row.get("Active", True))

        p_key = (item.id, branch.id)
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
            db.add(Pricing(
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
            ))
            counters["pricing_created"] += 1

    await db.flush()

    # ----------------------------------------------------------------
    # Phase 3: BOM  (auto-create Godown if missing; Inventory Item MUST exist)
    # ----------------------------------------------------------------
    all_branch_ids = [b.id for b in branches_map.values()]
    inventory_map = await _load_inventory_items(db, all_branch_ids)
    godowns_map = await _load_godowns(db, all_branch_ids)
    bom_map = await _load_existing_bom(db)

    for idx, row in bom_df.iterrows():
        menu_item_name = _safe_str(row.get("Menu Item"))
        inv_item_name = _safe_str(row.get("Inventory Item"))
        godown_name = _safe_str(row.get("Godown"))
        branch_code = _safe_str(row.get("Branch Code")).upper()

        if not menu_item_name or not inv_item_name or not godown_name:
            continue

        branch = branches_map.get(branch_code)
        if branch is None:
            raise HTTPException(400, f"Branch Code '{branch_code}' not found.")

        item = items_map.get((menu_item_name.lower(), branch.id))
        if item is None:
            raise HTTPException(
                400,
                f"Menu Item '{menu_item_name}' not found for Branch Code '{branch_code}'.",
            )

        # Inventory Item must already exist — cannot safely auto-create
        # (requires unit, cost, vendor, stock info that cannot be inferred).
        inv_item = inventory_map.get((inv_item_name.lower(), branch.id))
        if inv_item is None:
            raise HTTPException(
                400,
                f"Inventory Item '{inv_item_name}' not found for branch '{branch_code}'. "
                "Please upload Inventory before importing BOM.",
            )

        # Auto-create Godown if it does not exist.
        godown = await _find_or_create_godown(
            db=db,
            godown_name=godown_name,
            branch_id=branch.id,
            godowns_map=godowns_map,
            counters=counters,
        )

        try:
            quantity = float(row.get("Quantity"))
        except (TypeError, ValueError):
            raise HTTPException(400, f"Invalid quantity for BOM row {idx + 2}.")
        if quantity <= 0:
            raise HTTPException(400, f"Quantity must be positive (row {idx + 2}).")

        bom_key = (item.id, inv_item.id, godown.id)
        existing_bom = bom_map.get(bom_key)

        if existing_bom:
            existing_bom.quantity_required = quantity
            counters["bom_updated"] += 1
        else:
            db.add(ItemIngredient(
                item_id=item.id,
                inventory_item_id=inv_item.id,
                godown_id=godown.id,
                quantity_required=quantity,
            ))
            counters["bom_created"] += 1

    return UploadResult(
        message="Menu uploaded successfully",
        counts=counters,
    )


_VALID_STATUS = {"in_stock", "low_stock", "out_of_stock"}
# NOTE: row_category is intentionally open — it accepts any non-empty string.
# This ensures that files exported by this system (which may contain values like
# 'produce', 'dry_goods', etc.) can always be re-imported without validation failure.
# We only fall back to "other" when the field is blank.


async def _process_inventory(
    db: AsyncSession,
    sheets: dict[str, pd.DataFrame],
    client_id: int,
) -> UploadResult:
    """Business logic for the 'inventory' module.

    Auto-creates missing Godowns (case-insensitive dedup).
    row_category accepts any non-empty string — no whitelist restriction.
    """
    inv_df = sheets["Inventory_Items"]

    branches_map = await _load_branches(db, client_id)
    all_branch_ids = [b.id for b in branches_map.values()]
    godowns_map = await _load_godowns(db, all_branch_ids)
    inventory_map = await _load_inventory_items(db, all_branch_ids)

    # Shared counters dict — helpers mutate this in-place.
    counters: dict[str, int] = {
        "godowns_created": 0,
        "godowns_skipped": 0,
        "items_created": 0,
        "items_updated": 0,
        "errors": 0,
    }

    for idx, row in inv_df.iterrows():
        name = _safe_str(row.get("Name"))
        branch_code = _safe_str(row.get("Branch Code")).upper()
        unit = _safe_str(row.get("Unit"))

        if not name:
            continue
        if not branch_code:
            raise HTTPException(400, f"Row {idx + 2}: 'Branch Code' cannot be empty.")
        if not unit:
            raise HTTPException(400, f"Row {idx + 2}: 'Unit' cannot be empty.")

        branch = branches_map.get(branch_code)
        if branch is None:
            raise HTTPException(400, f"Branch '{branch_code}' not found.")

        # Auto-create Godown if it is specified but does not exist.
        godown = None
        godown_name = _safe_str(row.get("Godown"))
        if godown_name:
            godown = await _find_or_create_godown(
                db=db,
                godown_name=godown_name,
                branch_id=branch.id,
                godowns_map=godowns_map,
                counters=counters,
            )

        # Accept any non-empty category string; default to "other" when blank.
        # This makes re-import of exported files always succeed.
        row_category = _safe_str(row.get("Category")) or "other"

        display_unit = _safe_str(row.get("Display Unit")) or "piece"
        conversion_factor = _safe_float(row.get("Conversion Factor", 1.0), "Conversion Factor")
        if conversion_factor <= 0:
            raise HTTPException(400, f"Row {idx + 2}: 'Conversion Factor' must be positive.")

        stock_qty = _safe_float(row.get("Stock Qty", 0), "Stock Qty")
        reorder_level = _safe_float(row.get("Reorder Level", 0), "Reorder Level")
        cost_per_unit = _safe_float(row.get("Cost Per Unit", 0), "Cost Per Unit")
        vendor_name = _safe_str(row.get("Vendor Name")) or None
        vendor_phone = _safe_str(row.get("Vendor Phone")) or None

        status_raw = _safe_str(row.get("Status")) or "in_stock"
        if status_raw not in _VALID_STATUS:
            raise HTTPException(
                400,
                f"Row {idx + 2}: 'Status' must be one of {sorted(_VALID_STATUS)}, got '{status_raw}'.",
            )

        key = (name.lower(), branch.id)
        existing = inventory_map.get(key)

        if existing:
            existing.unit = unit
            existing.display_unit = display_unit
            existing.conversion_factor = conversion_factor
            existing.row_category = row_category
            existing.stock_qty = stock_qty
            existing.reorder_level = reorder_level
            existing.cost_per_unit = cost_per_unit
            existing.vendor_name = vendor_name
            existing.vendor_phone = vendor_phone
            existing.status = status_raw
            if godown is not None:
                existing.godown_id = godown.id
            counters["items_updated"] += 1
        else:
            item = InventoryItem(
                name=name,
                branch_id=branch.id,
                godown_id=godown.id if godown else None,
                unit=unit,
                display_unit=display_unit,
                conversion_factor=conversion_factor,
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
            counters["items_created"] += 1

    return UploadResult(
        message="Inventory uploaded successfully",
        counts=counters,
    )


async def _process_category(
    db: AsyncSession,
    sheets: dict[str, pd.DataFrame],
    client_id: int,
) -> UploadResult:
    """Business logic for the 'category' module."""
    cat_df = sheets["Categories"]

    branches_map = await _load_branches(db, client_id)
    categories_map = await _load_categories(db, client_id)

    created = updated = 0

    for idx, row in cat_df.iterrows():
        name = _safe_str(row.get("Name"))
        branch_code = _safe_str(row.get("Branch Code")).upper()

        if not name:
            continue
        if not branch_code:
            raise HTTPException(400, f"Row {idx + 2}: 'Branch Code' cannot be empty.")

        branch = branches_map.get(branch_code)
        if branch is None:
            raise HTTPException(400, f"Branch '{branch_code}' not found.")

        is_active = _safe_bool(row.get("Active", True))
        key = (name.lower(), branch.id)
        existing = categories_map.get(key)

        if existing:
            existing.is_active = is_active
            updated += 1
        else:
            category = Category(
                name=name,
                branch_id=branch.id,
                client_id=client_id,
            )
            db.add(category)
            categories_map[key] = category
            created += 1

    return UploadResult(
        message="Categories uploaded successfully",
        counts={"categories_created": created, "categories_updated": updated},
    )


# Patch handlers into the config now that functions are defined.
UPLOAD_CONFIG["menu"].handler = _process_menu
UPLOAD_CONFIG["inventory"].handler = _process_inventory
UPLOAD_CONFIG["category"].handler = _process_category


# ---------------------------------------------------------------------------
# BulkUploadService
# ---------------------------------------------------------------------------

class BulkUploadService:
    """
    Dispatcher + orchestrator for all bulk-upload modules.

    Adding a new module requires:
      1. A new entry in TEMPLATES
      2. A new entry in UPLOAD_CONFIG
      3. A new async _process_<module>()
    No changes needed here.
    """

    @staticmethod
    async def upload(
        db: AsyncSession,
        file: UploadFile,
        module: str,
        client_id: int,
    ) -> dict:
        module = module.lower()
        config = UPLOAD_CONFIG.get(module)
        if config is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown module '{module}'. Supported: {list(UPLOAD_CONFIG)}",
            )

        raw_bytes = await file.read()
        try:
            xls = pd.ExcelFile(io.BytesIO(raw_bytes))
        except Exception:
            raise HTTPException(status_code=400, detail="Could not parse uploaded file as Excel.")

        sheets: dict[str, pd.DataFrame] = {}
        for sheet_cfg in config.sheets:
            if sheet_cfg.name not in xls.sheet_names:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sheet '{sheet_cfg.name}' is missing from the uploaded file.",
                )
            df = xls.parse(sheet_cfg.name).dropna(how="all")

            missing_cols = [c for c in sheet_cfg.required_columns if c not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Column(s) {missing_cols} missing in sheet '{sheet_cfg.name}'.",
                )

            sheets[sheet_cfg.name] = df

        try:
            result: UploadResult = await config.handler(db, sheets, client_id)
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error during '{module}' upload: {exc}",
            ) from exc

        return result.to_dict()

    @staticmethod
    async def download_template(module: str) -> FileResponse:
        module = module.lower()

        if module not in TEMPLATES:
            raise HTTPException(
                status_code=400,
                detail=f"No template found for module '{module}'. Available: {list(TEMPLATES)}",
            )

        temp_dir = Path("temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / f"{module}_template.xlsx"

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            for sheet_name, sample_data in TEMPLATES[module].items():
                df = pd.DataFrame(sample_data)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                _auto_width_excel(writer, sheet_name)

        return FileResponse(
            path=str(file_path),
            filename=f"{module}_template.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Branch permission helper
# Defined here (above BulkExportService) so it is in scope when called.
# ---------------------------------------------------------------------------

async def get_allowed_branches(
    db: AsyncSession,
    client: Any,
) -> list[Branch]:
    """
    Return all branches owned by the authenticated client.
    """

    result = await db.execute(
        select(Branch).where(
            Branch.client_id == client.id
        )
    )

    branches = result.scalars().all()

    if not branches:
        raise HTTPException(
            status_code=403,
            detail="No branches found for this client."
        )

    return branches
    """
    Determine which Branch objects the authenticated client may access.

    Two scenarios:
      - client.all_branches is True  -> return every branch owned by this client.
      - otherwise                    -> return only the branches explicitly
                                        assigned via client.branch_ids (list[int]).

    Raises 403 if the resolved list is empty so callers never export
    zero-branch data silently.
    """
    if getattr(client, "all_branches", False):
        result = await db.execute(
            select(Branch).where(Branch.client_id == client.id)
        )
        branches = result.scalars().all()
    else:
        assigned_ids: list[int] = getattr(client, "branch_ids", []) or []
        if not assigned_ids:
            raise HTTPException(
                status_code=403,
                detail="No branches are assigned to your account.",
            )
        result = await db.execute(
            select(Branch).where(
                Branch.client_id == client.id,
                Branch.id.in_(assigned_ids),
            )
        )
        branches = result.scalars().all()

    if not branches:
        raise HTTPException(
            status_code=403,
            detail="No accessible branches found for your account.",
        )
    return list(branches)


# ---------------------------------------------------------------------------
# Generic Excel generator
# ---------------------------------------------------------------------------

def _build_excel_response(
    sheets: dict[str, pd.DataFrame],
    filename: str,
) -> FileResponse:
    """Write one worksheet per DataFrame into a temp .xlsx and return FileResponse."""
    if not sheets:
        raise HTTPException(status_code=404, detail="No data available for export.")

    temp_dir = Path("temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_path = temp_dir / filename

    try:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                _auto_width_excel(writer, sheet_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Excel file: {exc}",
        ) from exc

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Module-specific export handlers
# ---------------------------------------------------------------------------


async def _export_bill(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:
    """Export Bills for allowed branches."""
    result = await db.execute(
        select(Bill, Branch)
        .join(Branch, Bill.branch_id == Branch.id)
        .where(Bill.branch_id.in_(branch_ids))
    )
    rows = result.all()

    data = [
        {
            "Invoice No": bill.invoice_no,
            "Branch Code": branch.branch_code,
            "Order Type": bill.order_type,
            "Customer Name": bill.customer_name or "",
            "Customer Phone": bill.customer_phone or "",
            "Payment Status": bill.payment_status.value,   # enum → string
            "Payment Method": bill.payment_method or "",
            "Subtotal": bill.subtotal,
            "CGST %": bill.cgst_percent,
            "CGST Amount": bill.cgst_amount,
            "SGST %": bill.sgst_percent,
            "SGST Amount": bill.sgst_amount,
            "Service Charge %": bill.service_charge_percent,
            "Service Charge Amount": bill.service_charge_amount,
            "Tax Total": bill.tax_total,
            "Discount Amount": bill.discount_amount,
            "Round Off Amount": bill.round_off_amount,
            "Grand Total": bill.grand_total,
            "Paid Amount": bill.paid_amount,
            "Due Amount": bill.due_amount,
            "Offer Discount": bill.offer_discount,
            "Final Amount": bill.final_amount,
            "Notes": bill.notes or "",
            "Footer Message": bill.footer_message or "",
            "Billed At": bill.billed_at.strftime("%Y-%m-%d %H:%M:%S") if bill.billed_at else "",
        }
        for bill, branch in rows
    ]

    return {"Bills": pd.DataFrame(data)}



async def _export_menu(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:
    """Export Menu Items, Pricing, and BOM for allowed branches."""
    items_result = await db.execute(
        select(Item, Branch, Category)
        .join(Branch, Item.branch_id == Branch.id)
        .join(Category, Item.category_id == Category.id)
        .where(Item.branch_id.in_(branch_ids))
    )
    items_rows = items_result.all()

    menu_items_data = [
        {
            "Name": item.name,
            "Category": category.name,
            "Branch Code": branch.branch_code,
            "Active": item.is_active,
        }
        for item, branch, category in items_rows
    ]

    pricing_result = await db.execute(
        select(Pricing, Item, Branch)
        .join(Item, Pricing.item_id == Item.id)
        .join(Branch, Pricing.branch_id == Branch.id)
        .where(Pricing.branch_id.in_(branch_ids))
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
        for pricing, item, branch in pricing_rows
    ]

    bom_result = await db.execute(
        select(ItemIngredient, Item, InventoryItem, Godown, Branch)
        .join(Item, ItemIngredient.item_id == Item.id)
        .join(InventoryItem, ItemIngredient.inventory_item_id == InventoryItem.id)
        .join(Godown, ItemIngredient.godown_id == Godown.id)
        .join(Branch, Item.branch_id == Branch.id)
        .where(Item.branch_id.in_(branch_ids))
    )
    bom_rows = bom_result.all()

    bom_data = [
        {
            "Menu Item": item.name,
            "Branch Code": branch.branch_code,
            "Inventory Item": inv_item.name,
            "Godown": godown.name,
            "Quantity": ingredient.quantity_required,
        }
        for ingredient, item, inv_item, godown, branch in bom_rows
    ]

    return {
        "Menu_Items": pd.DataFrame(menu_items_data),
        "Pricing": pd.DataFrame(pricing_data),
        "BOM": pd.DataFrame(bom_data),
    }


async def _export_inventory(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:
    """Export Inventory Items for allowed branches."""
    result = await db.execute(
        select(InventoryItem, Branch, Godown)
        .join(Branch, InventoryItem.branch_id == Branch.id)
        .outerjoin(Godown, InventoryItem.godown_id == Godown.id)
        .where(InventoryItem.branch_id.in_(branch_ids))
    )
    rows = result.all()

    data = [
        {
            "Name": inv.name,
            "Branch Code": branch.branch_code,
            "Godown": godown.name if godown else "",
            "Category": inv.row_category,
            "Unit": inv.unit,
            "Display Unit": inv.display_unit,
            "Conversion Factor": inv.conversion_factor,
            "Stock Qty": inv.stock_qty,
            "Reorder Level": inv.reorder_level,
            "Cost Per Unit": inv.cost_per_unit,
            "Vendor Name": inv.vendor_name or "",
            "Vendor Phone": inv.vendor_phone or "",
            "Status": inv.status,
        }
        for inv, branch, godown in rows
    ]

    return {"Inventory_Items": pd.DataFrame(data)}


async def _export_category(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:
    """Export Categories for allowed branches."""
    result = await db.execute(
        select(Category, Branch)
        .join(Branch, Category.branch_id == Branch.id)
        .where(Category.branch_id.in_(branch_ids))
    )
    rows = result.all()

    data = [
        {
            "Name": category.name,
            "Branch Code": branch.branch_code,
            "Active": category.is_active,
        }
        for category, branch in rows
    ]

    return {"Categories": pd.DataFrame(data)}



async def _export_all_reports(
    db: AsyncSession,
    branch_ids: list[int],
    client_id: int,
) -> dict[str, pd.DataFrame]:
    """Export all reports into a single Excel with one sheet each."""
    from datetime import datetime, timedelta
    from sqlalchemy import func

    from app.accounts.order.model import Order, OrderItem
    from app.accounts.payment.model import Payment

    # ----------------------------------------------------------------
    # Sheet 1: Bills
    # ----------------------------------------------------------------
    bills_result = await db.execute(
        select(Bill, Branch)
        .join(Branch, Bill.branch_id == Branch.id)
        .where(Bill.branch_id.in_(branch_ids))
    )
    bills_rows = bills_result.all()

    bills_data = [
        {
            "Invoice No": bill.invoice_no,
            "Branch Code": branch.branch_code,
            "Order Type": bill.order_type,
            "Customer Name": bill.customer_name or "",
            "Customer Phone": bill.customer_phone or "",
            "Payment Status": bill.payment_status.value,
            "Payment Method": bill.payment_method or "",
            "Subtotal": bill.subtotal,
            "CGST %": bill.cgst_percent,
            "CGST Amount": bill.cgst_amount,
            "SGST %": bill.sgst_percent,
            "SGST Amount": bill.sgst_amount,
            "Service Charge %": bill.service_charge_percent,
            "Service Charge Amount": bill.service_charge_amount,
            "Tax Total": bill.tax_total,
            "Discount Amount": bill.discount_amount,
            "Round Off Amount": bill.round_off_amount,
            "Grand Total": bill.grand_total,
            "Paid Amount": bill.paid_amount,
            "Due Amount": bill.due_amount,
            "Offer Discount": bill.offer_discount,
            "Final Amount": bill.final_amount,
            "Notes": bill.notes or "",
            "Billed At": bill.billed_at.strftime("%Y-%m-%d %H:%M:%S") if bill.billed_at else "",
        }
        for bill, branch in bills_rows
    ]

    # ----------------------------------------------------------------
    # Sheet 2: Financial Summary (per branch)
    # ----------------------------------------------------------------
    financial_data = []
    for bid in branch_ids:
        branch_obj = next((b for _, b in bills_rows if b.id == bid), None)
        branch_code = branch_obj.branch_code if branch_obj else str(bid)

        revenue = await db.scalar(
            select(func.coalesce(func.sum(Bill.grand_total), 0))
            .where(Bill.branch_id == bid, Bill.payment_status == PaymentStatus.complete)
        ) or 0

        paid_orders = await db.scalar(
            select(func.count(Bill.id))
            .where(Bill.branch_id == bid, Bill.payment_status == PaymentStatus.complete)
        ) or 0

        tax_total = await db.scalar(
            select(func.coalesce(func.sum(Bill.tax_total + Bill.service_charge_amount), 0))
            .where(Bill.branch_id == bid, Bill.payment_status == PaymentStatus.complete)
        ) or 0

        financial_data.append({
            "Branch Code": branch_code,
            "Total Revenue": round(float(revenue), 2),
            "Paid Orders": paid_orders,
            "Tax Collected": round(float(tax_total), 2),
            "Avg Order Value": round(float(revenue) / paid_orders, 2) if paid_orders else 0,
        })

    # ----------------------------------------------------------------
    # Sheet 3: Sales Summary — this week per branch
    # ----------------------------------------------------------------
    today = datetime.utcnow()
    start_of_week = (today - timedelta(days=today.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_of_week = (start_of_week + timedelta(days=5)).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )

    sales_data = []
    for bid in branch_ids:
        branch_obj = next((b for _, b in bills_rows if b.id == bid), None)
        branch_code = branch_obj.branch_code if branch_obj else str(bid)

        week_orders = await db.scalar(
            select(func.count(Order.id))
            .where(
                Order.branch_id == bid,
                Order.created_at >= start_of_week,
                Order.created_at <= end_of_week,
            )
        ) or 0

        week_revenue = await db.scalar(
            select(func.coalesce(func.sum(Bill.grand_total), 0))
            .where(
                Bill.branch_id == bid,
                Bill.created_at >= start_of_week,
                Bill.created_at <= end_of_week,
                Bill.payment_status == PaymentStatus.complete,
            )
        ) or 0

        sales_data.append({
            "Branch Code": branch_code,
            "This Week Orders": week_orders,
            "This Week Revenue": round(float(week_revenue), 2),
            "Avg Daily Orders": round(week_orders / 6, 1),
        })

    # ----------------------------------------------------------------
    # Sheet 4: Top Selling Items
    # ----------------------------------------------------------------
    top_items_result = await db.execute(
        select(
            Item.name.label("item_name"),
            func.sum(OrderItem.quantity).label("quantity_sold"),
        )
        .join(OrderItem, OrderItem.item_id == Item.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Bill, Bill.order_id == Order.id)
        .where(
            Order.branch_id.in_(branch_ids),
            Bill.payment_status == PaymentStatus.complete,
        )
        .group_by(Item.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(50)
    )
    top_items_rows = top_items_result.all()
    total_qty = sum(r.quantity_sold for r in top_items_rows)

    top_items_data = [
        {
            "Item Name": r.item_name,
            "Quantity Sold": r.quantity_sold,
            "% of Total": round((r.quantity_sold / total_qty) * 100, 2) if total_qty else 0,
        }
        for r in top_items_rows
    ]

    # ----------------------------------------------------------------
    # Sheet 5: Category Distribution
    # ----------------------------------------------------------------
    cat_result = await db.execute(
        select(
            Category.name.label("category_name"),
            Branch.branch_code,
            func.count(Item.id).label("item_count"),
        )
        .outerjoin(Item, Item.category_id == Category.id)
        .join(Branch, Category.branch_id == Branch.id)
        .where(Category.branch_id.in_(branch_ids))
        .group_by(Category.name, Branch.branch_code)
        .order_by(func.count(Item.id).desc())
    )
    cat_rows = cat_result.all()
    total_cat_items = sum(r.item_count for r in cat_rows)

    category_data = [
        {
            "Branch Code": r.branch_code,
            "Category": r.category_name,
            "Item Count": r.item_count,
            "% of Menu": round((r.item_count / total_cat_items) * 100, 2) if total_cat_items else 0,
        }
        for r in cat_rows
    ]

    # ----------------------------------------------------------------
    # Sheet 6: Inventory Summary
    # ----------------------------------------------------------------
    inv_result = await db.execute(
        select(InventoryItem, Branch, Godown)
        .join(Branch, InventoryItem.branch_id == Branch.id)
        .outerjoin(Godown, InventoryItem.godown_id == Godown.id)
        .where(InventoryItem.branch_id.in_(branch_ids))
    )
    inv_rows = inv_result.all()

    inventory_data = [
        {
            "Branch Code": branch.branch_code,
            "Name": inv.name,
            "Category": inv.row_category,
            "Godown": godown.name if godown else "",
            "Unit": inv.unit,
            "Stock Qty": inv.stock_qty,
            "Reorder Level": inv.reorder_level,
            "Cost Per Unit": inv.cost_per_unit,
            "Stock Value": round((inv.stock_qty or 0) * (inv.cost_per_unit or 0), 2),
            "Status": inv.status,
            "Vendor Name": inv.vendor_name or "",
            "Vendor Phone": inv.vendor_phone or "",
        }
        for inv, branch, godown in inv_rows
    ]

    # ----------------------------------------------------------------
    # Sheet 7: Payment Method Totals
    # ----------------------------------------------------------------
    payments_result = await db.execute(
        select(Payment, Branch)
        .join(Branch, Payment.branch_id == Branch.id)
        .where(Branch.id.in_(branch_ids))
    )
    payments_rows = payments_result.all()

    payment_totals: dict[str, dict] = {}
    for payment, branch in payments_rows:
        code = branch.branch_code
        if code not in payment_totals:
            payment_totals[code] = {
                "Branch Code": code,
                "Cash Orders": 0, "Cash Total": 0,
                "UPI Orders": 0, "UPI Total": 0,
                "Card Orders": 0, "Card Total": 0,
                "Credit Orders": 0, "Credit Total": 0,
                "Grand Total": 0,
            }
        for item in (payment.payment_breakdown or []):
            method = (item.get("payment_method") or "").lower()
            amount = float(item.get("payment_amount", 0))
            if method == "cash":
                payment_totals[code]["Cash Orders"] += 1
                payment_totals[code]["Cash Total"] += amount
            elif method == "upi":
                payment_totals[code]["UPI Orders"] += 1
                payment_totals[code]["UPI Total"] += amount
            elif method == "card":
                payment_totals[code]["Card Orders"] += 1
                payment_totals[code]["Card Total"] += amount
            elif method == "credit":
                payment_totals[code]["Credit Orders"] += 1
                payment_totals[code]["Credit Total"] += amount

    for row in payment_totals.values():
        row["Grand Total"] = round(
            row["Cash Total"] + row["UPI Total"] + row["Card Total"] + row["Credit Total"], 2
        )
        for key in ("Cash Total", "UPI Total", "Card Total", "Credit Total"):
            row[key] = round(row[key], 2)

    payment_data = list(payment_totals.values())

    # ----------------------------------------------------------------
    # Assemble all sheets
    # ----------------------------------------------------------------
    return {
        "Bills": pd.DataFrame(bills_data),
        "Financial_Summary": pd.DataFrame(financial_data),
        "Sales_Summary": pd.DataFrame(sales_data),
        "Top_Selling_Items": pd.DataFrame(top_items_data),
        "Category_Distribution": pd.DataFrame(category_data),
        "Inventory": pd.DataFrame(inventory_data),
        "Payment_Totals": pd.DataFrame(payment_data),
    }


# ---------------------------------------------------------------------------
# Export handler registry
# ---------------------------------------------------------------------------

ExportHandler = Callable  # async (db, branch_ids, client_id) -> dict[str, pd.DataFrame]

EXPORT_HANDLERS: dict[str, ExportHandler] = {
    "menu": _export_menu,
    "inventory": _export_inventory,
    "category": _export_category,
    "bill": _export_bill,
    "all_reports": _export_all_reports,
}


# ---------------------------------------------------------------------------
# BulkExportService
# ---------------------------------------------------------------------------

class BulkExportService:
    """
    Generic export orchestrator.

    Adding a new export module requires:
      1. A new async _export_<module>(db, branch_ids, client_id) function.
      2. A new entry in EXPORT_HANDLERS.
    No changes needed here.
    """

    @staticmethod
    async def export(
        db: AsyncSession,
        module: str,
        client: Any,
    ) -> FileResponse:
        module = module.lower()
        handler = EXPORT_HANDLERS.get(module)
        if handler is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown export module '{module}'. "
                    f"Supported: {list(EXPORT_HANDLERS)}"
                ),
            )

        print("CLIENT:", client)
        print("CLIENT ID:", client.id)
        print("ALL BRANCHES:", getattr(client, "all_branches", None))
        print("BRANCH IDS:", getattr(client, "branch_ids", None))

        # get_allowed_branches is defined above in this same module — no import needed.
        allowed_branches = await get_allowed_branches(db, client)
        branch_ids = [b.id for b in allowed_branches]

        try:
            sheets: dict[str, pd.DataFrame] = await handler(db, branch_ids, client.id)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error during '{module}' export: {exc}",
            ) from exc

        total_rows = sum(len(df) for df in sheets.values())
        if total_rows == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for module '{module}' in your accessible branches.",
            )

        from datetime import date
        filename = f"{module}_export_{date.today()}.xlsx"
        return _build_excel_response(sheets, filename)
