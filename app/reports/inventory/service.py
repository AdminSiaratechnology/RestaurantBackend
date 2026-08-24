# app/reports/inventory/service.py

import io
from datetime import date
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func, case
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.inventory.model import InventoryItem, Godown
from app.reports.constants import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    ALIGN_RIGHT,
    NUM_FMT_CURRENCY,
    NUM_FMT_QTY,
    DEFAULT_ITEM_EMOJIS,
)
from app.reports.helpers import (
    resolve_date_range,
    validate_and_get_scope,
    safe_float,
    safe_int,
    safe_str,
)
from app.reports.export_engine import ExcelReportBuilder


class InventoryReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        category: Optional[str] = None,
        godown_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return InventoryReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        conditions = [InventoryItem.branch_id.in_(branch_ids)]
        if category and category != "all":
            conditions.append(InventoryItem.row_category.ilike(f"%{category}%"))
        if godown_id:
            conditions.append(InventoryItem.godown_id == godown_id)
        if status_filter and status_filter != "all":
            if status_filter == "low_stock":
                conditions.extend([InventoryItem.stock_qty > 0, InventoryItem.stock_qty <= InventoryItem.reorder_level])
            elif status_filter == "out_of_stock":
                conditions.append(InventoryItem.stock_qty <= 0)
            elif status_filter == "in_stock":
                conditions.append(InventoryItem.stock_qty > InventoryItem.reorder_level)

        # 1. Summary Aggregations
        summary_query = select(
            func.count(InventoryItem.id).label("total_items"),
            func.coalesce(func.sum(InventoryItem.stock_qty), 0).label("total_stock_quantity"),
            func.coalesce(
                func.sum(
                    func.coalesce(InventoryItem.stock_qty, 0) * func.coalesce(InventoryItem.cost_per_unit, 0)
                ),
                0,
            ).label("total_stock_value"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (InventoryItem.stock_qty > 0)
                            & (InventoryItem.stock_qty <= InventoryItem.reorder_level),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("low_stock_items"),
            func.coalesce(
                func.sum(
                    case(
                        (InventoryItem.stock_qty <= 0, 1),
                        else_=0,
                    )
                ),
                0,
            ).label("out_of_stock_items"),
        ).where(InventoryItem.branch_id.in_(branch_ids))

        summary_res = await db.execute(summary_query)
        s_row = summary_res.one()

        summary_data = {
            "total_items": safe_int(s_row.total_items),
            "total_stock_quantity": round(safe_float(s_row.total_stock_quantity), 2),
            "low_stock_items": safe_int(s_row.low_stock_items),
            "out_of_stock_items": safe_int(s_row.out_of_stock_items),
            "total_stock_value": round(safe_float(s_row.total_stock_value), 2),
            "stock_value": round(safe_float(s_row.total_stock_value), 2),
        }

        # 2. Charts: Stock Value by Category
        cat_query = (
            select(
                InventoryItem.row_category.label("category"),
                func.count(InventoryItem.id).label("item_count"),
                func.coalesce(
                    func.sum(
                        func.coalesce(InventoryItem.stock_qty, 0) * func.coalesce(InventoryItem.cost_per_unit, 0)
                    ),
                    0,
                ).label("stock_value"),
            )
            .where(InventoryItem.branch_id.in_(branch_ids))
            .group_by(InventoryItem.row_category)
            .order_by(func.sum(InventoryItem.stock_qty * InventoryItem.cost_per_unit).desc())
        )
        cat_res = await db.execute(cat_query)
        cat_rows = cat_res.all()

        chart_data = [
            {
                "label": (row.category or "Other").title(),
                "amount": round(safe_float(row.stock_value), 2),
                "quantity": safe_int(row.item_count),
            }
            for row in cat_rows
        ]

        # 3. Top High Value Stock Items
        top_query = (
            select(
                InventoryItem.id,
                InventoryItem.name,
                InventoryItem.stock_qty,
                (InventoryItem.stock_qty * InventoryItem.cost_per_unit).label("value"),
            )
            .where(InventoryItem.branch_id.in_(branch_ids))
            .order_by((InventoryItem.stock_qty * InventoryItem.cost_per_unit).desc())
            .limit(10)
        )
        top_res = await db.execute(top_query)
        top_rows = top_res.all()
        tot_val = summary_data["total_stock_value"]

        top_items = []
        for idx, item in enumerate(top_rows, start=1):
            val = safe_float(item.value)
            pct = round((val / tot_val) * 100, 2) if tot_val > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": item.id,
                    "name": item.name,
                    "icon": DEFAULT_ITEM_EMOJIS[(idx - 1) % len(DEFAULT_ITEM_EMOJIS)],
                    "quantity": round(safe_float(item.stock_qty), 2),
                    "amount": round(val, 2),
                    "percent": pct,
                }
            )

        # 4. Detailed Data Rows
        total_records_res = await db.execute(select(func.count(InventoryItem.id)).where(*conditions))
        total_records = total_records_res.scalar() or 0

        offset = max(page - 1, 0) * page_size
        items_query = (
            select(InventoryItem)
            .options(joinedload(InventoryItem.godown))
            .where(*conditions)
            .order_by(InventoryItem.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        items_res = await db.execute(items_query)
        items = items_res.scalars().all()

        rows = []
        for idx, it in enumerate(items, start=offset + 1):
            godown_name = it.godown.name if it.godown else f"Godown #{it.godown_id}" if it.godown_id else "Main Godown"
            qty = safe_float(it.stock_qty)
            reorder = safe_float(it.reorder_level)
            cpu = safe_float(it.cost_per_unit)
            val = round(qty * cpu, 2)

            # Determine human readable status
            if qty <= 0:
                status_txt = "Out of Stock"
            elif qty <= reorder:
                status_txt = "Low Stock"
            else:
                status_txt = "In Stock"

            rows.append(
                {
                    "sr_no": idx,
                    "id": it.id,
                    "branch_id": it.branch_id,
                    "name": it.name,
                    "category": (it.row_category or "Other").title(),
                    "godown": godown_name,
                    "unit": it.display_unit or it.unit or "Unit",
                    "stock_quantity": round(qty, 2),
                    "reorder_level": round(reorder, 2),
                    "cost_per_unit": round(cpu, 2),
                    "stock_value": val,
                    "status": status_txt,
                    "vendor_name": it.vendor_name or "—",
                    "vendor_phone": it.vendor_phone or "—",
                    "last_restocked": it.last_restocked.strftime("%d-%m-%Y") if it.last_restocked else "—",
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "inventory",
            "scope": {
                **scope_meta,
                "date_from": f_date,
                "date_to": t_date,
            },
            "summary": summary_data,
            "chart": chart_data,
            "charts": {
                "category": chart_data,
                "7d": chart_data,
                "month": chart_data,
                "today": chart_data,
            },
            "top_items": top_items,
            "rows": rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_records,
                "total_pages": total_pages,
            },
        }

    @staticmethod
    def _empty_response(scope_meta, f_date, t_date, page, page_size):
        return {
            "success": True,
            "report": "inventory",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_items": 0,
                "total_stock_quantity": 0.0,
                "low_stock_items": 0,
                "out_of_stock_items": 0,
                "total_stock_value": 0.0,
                "stock_value": 0.0,
            },
            "chart": [],
            "charts": {"category": [], "7d": [], "month": [], "today": []},
            "top_items": [],
            "rows": [],
            "pagination": {"page": page, "page_size": page_size, "total": 0, "total_pages": 1},
        }

    @staticmethod
    async def export_excel(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        category: Optional[str] = None,
        godown_id: Optional[int] = None,
    ) -> Tuple[io.BytesIO, str]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        conditions = [InventoryItem.branch_id.in_(branch_ids)]
        if category and category != "all":
            conditions.append(InventoryItem.row_category.ilike(f"%{category}%"))
        if godown_id:
            conditions.append(InventoryItem.godown_id == godown_id)

        items_res = await db.execute(
            select(InventoryItem)
            .options(joinedload(InventoryItem.godown))
            .where(*conditions)
            .order_by(InventoryItem.row_category.asc(), InventoryItem.name.asc())
        )
        items = items_res.scalars().all()

        tot_items = len(items)
        tot_qty = sum(safe_float(it.stock_qty) for it in items)
        tot_val = sum(safe_float(it.stock_qty) * safe_float(it.cost_per_unit) for it in items)
        low_stock_count = sum(1 for it in items if safe_float(it.stock_qty) > 0 and safe_float(it.stock_qty) <= safe_float(it.reorder_level))
        out_stock_count = sum(1 for it in items if safe_float(it.stock_qty) <= 0)

        title = f"Inventory Report - {scope_meta['branch_name']}" if not scope_meta['is_all_branches'] else f"Inventory Report - {scope_meta['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope_meta["scope_name"],
            from_date=f_date,
            to_date=t_date,
        )

        # 1. Sheet 1: Inventory Summary
        kpis = [
            ("TOTAL ITEMS", str(tot_items), False),
            ("TOTAL STOCK QUANTITY", f"{tot_qty:,.2f}", False),
            ("LOW STOCK ITEMS", str(low_stock_count), False),
            ("OUT OF STOCK ITEMS", str(out_stock_count), False),
            ("TOTAL STOCK VALUE", f"₹{tot_val:,.2f}", True),
        ]

        summary_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Category", ALIGN_LEFT, 18),
            ("Item Name", ALIGN_LEFT, 26),
            ("Godown", ALIGN_LEFT, 20),
            ("Unit", ALIGN_CENTER, 12),
            ("Stock Qty", ALIGN_RIGHT, 14),
            ("Reorder Level", ALIGN_RIGHT, 14),
            ("Cost / Unit (₹)", ALIGN_RIGHT, 16),
            ("Stock Value (₹)", ALIGN_RIGHT, 18),
            ("Status", ALIGN_CENTER, 16),
            ("Vendor", ALIGN_LEFT, 24),
        ]

        summary_rows = []
        for idx, it in enumerate(items, start=1):
            g_name = it.godown.name if it.godown else (f"Godown #{it.godown_id}" if it.godown_id else "Main Godown")
            qty = safe_float(it.stock_qty)
            reorder = safe_float(it.reorder_level)
            cpu = safe_float(it.cost_per_unit)
            val = round(qty * cpu, 2)
            status_txt = "Out of Stock" if qty <= 0 else ("Low Stock" if qty <= reorder else "In Stock")

            summary_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (it.branch_id, ALIGN_CENTER, None),
                    ((it.row_category or "Other").title(), ALIGN_LEFT, None),
                    (it.name, ALIGN_LEFT, None),
                    (g_name, ALIGN_LEFT, None),
                    (it.display_unit or it.unit or "Unit", ALIGN_CENTER, None),
                    (qty, ALIGN_RIGHT, NUM_FMT_QTY),
                    (reorder, ALIGN_RIGHT, NUM_FMT_QTY),
                    (cpu, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (val, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (status_txt, ALIGN_CENTER, None),
                    (it.vendor_name or "—", ALIGN_LEFT, None),
                ]
            )

        summary_totals = {
            7: (tot_qty, NUM_FMT_QTY),
            10: (tot_val, NUM_FMT_CURRENCY),
        }

        builder.add_summary_sheet(
            sheet_title="Inventory Summary",
            kpis=kpis,
            headers=summary_headers,
            data_rows=summary_rows,
            totals_row=summary_totals,
            empty_message="No inventory records found for the selected filters.",
        )

        # 2. Sheet 2: Low Stock & Reorder Alert List
        low_items = [it for it in items if safe_float(it.stock_qty) <= safe_float(it.reorder_level)]
        detail_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Item Name", ALIGN_LEFT, 26),
            ("Category", ALIGN_LEFT, 18),
            ("Godown", ALIGN_LEFT, 20),
            ("Current Stock", ALIGN_RIGHT, 14),
            ("Reorder Level", ALIGN_RIGHT, 14),
            ("Shortage Qty", ALIGN_RIGHT, 14),
            ("Cost / Unit (₹)", ALIGN_RIGHT, 16),
            ("Est. Reorder Cost (₹)", ALIGN_RIGHT, 20),
            ("Vendor Name", ALIGN_LEFT, 22),
            ("Vendor Contact", ALIGN_CENTER, 16),
        ]

        detail_rows = []
        tot_reorder_cost = 0.0
        for idx, it in enumerate(low_items, start=1):
            g_name = it.godown.name if it.godown else (f"Godown #{it.godown_id}" if it.godown_id else "Main Godown")
            qty = safe_float(it.stock_qty)
            reorder = safe_float(it.reorder_level)
            cpu = safe_float(it.cost_per_unit)
            shortage = max(reorder - qty, 0.0)
            reorder_cost = round(shortage * cpu, 2)
            tot_reorder_cost += reorder_cost

            detail_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (it.branch_id, ALIGN_CENTER, None),
                    (it.name, ALIGN_LEFT, None),
                    ((it.row_category or "Other").title(), ALIGN_LEFT, None),
                    (g_name, ALIGN_LEFT, None),
                    (qty, ALIGN_RIGHT, NUM_FMT_QTY),
                    (reorder, ALIGN_RIGHT, NUM_FMT_QTY),
                    (shortage, ALIGN_RIGHT, NUM_FMT_QTY),
                    (cpu, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (reorder_cost, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (it.vendor_name or "—", ALIGN_LEFT, None),
                    (it.vendor_phone or "—", ALIGN_CENTER, None),
                ]
            )

        detail_totals = {
            10: (tot_reorder_cost, NUM_FMT_CURRENCY),
        }

        builder.add_details_sheet(
            sheet_title="Low Stock Alerts",
            details_header_title="⚠️  LOW STOCK & REORDER ALERTS",
            headers=detail_headers,
            data_rows=detail_rows,
            totals_row=detail_totals,
            empty_message="All items are currently adequately stocked above reorder levels.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Inventory_Report_{branch_tag}_{f_date.strftime('%Y%m%d')}_{t_date.strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
