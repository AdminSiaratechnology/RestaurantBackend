# app/reports/item/service.py

import io
from datetime import date, datetime
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.item.model import Item
from app.accounts.category.model import Category
from app.accounts.order.model import Order, OrderItem
from app.accounts.pricing.model import Pricing
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


class ItemReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        category_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return ItemReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        # Item sales aggregations
        conditions = [
            Order.branch_id.in_(branch_ids),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ]

        if category_id:
            conditions.append(Item.category_id == category_id)

        sales_query = (
            select(
                Item.id,
                Item.name,
                Item.branch_id,
                Item.food_type,
                Category.name.label("category_name"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("sold_qty"),
                func.coalesce(func.sum(OrderItem.total_price), 0).label("sold_amount"),
                func.avg(OrderItem.unit_price).label("avg_unit_price"),
            )
            .join(OrderItem, OrderItem.item_id == Item.id)
            .join(Order, Order.id == OrderItem.order_id)
            .outerjoin(Category, Category.id == Item.category_id)
            .where(*conditions)
            .group_by(Item.id, Item.name, Item.branch_id, Item.food_type, Category.name)
            .order_by(func.sum(OrderItem.total_price).desc())
        )
        sales_res = await db.execute(sales_query)
        sales_rows = sales_res.all()

        tot_items_sold_qty = sum(safe_float(r.sold_qty) for r in sales_rows)
        tot_item_sales_amount = sum(safe_float(r.sold_amount) for r in sales_rows)
        top_selling_item_name = sales_rows[0].name if sales_rows else "None"
        avg_price = (
            round(tot_item_sales_amount / tot_items_sold_qty, 2)
            if tot_items_sold_qty > 0
            else 0.0
        )

        # Count total active menu items
        menu_items_count = await db.scalar(
            select(func.count(Item.id)).where(Item.branch_id.in_(branch_ids))
        ) or len(sales_rows)

        summary_data = {
            "total_items_sold": round(tot_items_sold_qty, 2),
            "total_menu_items": menu_items_count,
            "total_items": menu_items_count,
            "top_selling_item": top_selling_item_name,
            "total_item_sales": round(tot_item_sales_amount, 2),
            "average_item_price": avg_price,
        }

        # Charts: Top 10 items
        chart_data = []
        for r in sales_rows[:10]:
            chart_data.append(
                {
                    "label": r.name,
                    "amount": round(safe_float(r.sold_amount), 2),
                    "quantity": round(safe_float(r.sold_qty), 2),
                }
            )

        top_items = []
        for idx, item in enumerate(chart_data, start=1):
            amt = item["amount"]
            pct = round((amt / tot_item_sales_amount) * 100, 2) if tot_item_sales_amount > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": sales_rows[idx - 1].id if idx <= len(sales_rows) else idx,
                    "name": item["label"],
                    "icon": DEFAULT_ITEM_EMOJIS[(idx - 1) % len(DEFAULT_ITEM_EMOJIS)],
                    "quantity": item["quantity"],
                    "amount": amt,
                    "percent": pct,
                }
            )

        # Paginated Rows
        branch_map = {b.id: b.name for b in branches}
        total_records = len(sales_rows)
        offset = max(page - 1, 0) * page_size
        paginated_rows = sales_rows[offset : offset + page_size]

        rows = []
        for idx, r in enumerate(paginated_rows, start=offset + 1):
            s_amt = safe_float(r.sold_amount)
            pct = round((s_amt / tot_item_sales_amount) * 100, 2) if tot_item_sales_amount > 0 else 0.0
            rows.append(
                {
                    "sr_no": idx,
                    "id": r.id,
                    "branch_id": r.branch_id,
                    "branch_name": branch_map.get(r.branch_id, f"Branch #{r.branch_id}"),
                    "name": r.name,
                    "category": r.category_name or "General",
                    "food_type": (r.food_type.value if hasattr(r.food_type, "value") else str(r.food_type or "Veg")).title(),
                    "unit_price": round(safe_float(r.avg_unit_price), 2),
                    "sold_quantity": round(safe_float(r.sold_qty), 2),
                    "sales_amount": round(s_amt, 2),
                    "percentage_of_total": pct,
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "item",
            "scope": {
                **scope_meta,
                "date_from": f_date,
                "date_to": t_date,
            },
            "summary": summary_data,
            "chart": chart_data,
            "charts": {
                "top_selling": chart_data,
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
            "report": "item",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_items_sold": 0.0,
                "total_menu_items": 0,
                "total_items": 0,
                "top_selling_item": "None",
                "total_item_sales": 0.0,
                "average_item_price": 0.0,
            },
            "chart": [],
            "charts": {"top_selling": [], "7d": [], "month": [], "today": []},
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
        category_id: Optional[int] = None,
    ) -> Tuple[io.BytesIO, str]:
        data = await ItemReportService.get_report_data(
            db=db,
            client_id=client_id,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            category_id=category_id,
            page=1,
            page_size=10000,
        )
        scope = data["scope"]
        summary = data["summary"]
        rows = data["rows"]

        title = f"Item Sales Report - {scope['branch_name']}" if not scope['is_all_branches'] else f"Item Sales Report - {scope['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope["scope_name"],
            from_date=scope["date_from"],
            to_date=scope["date_to"],
        )

        kpis = [
            ("TOTAL ITEMS SOLD", f"{summary['total_items_sold']:,.2f}", False),
            ("TOTAL MENU ITEMS", str(summary["total_menu_items"]), False),
            ("TOP SELLING ITEM", summary["top_selling_item"], False),
            ("AVERAGE PRICE", f"₹{summary['average_item_price']:,.2f}", False),
            ("TOTAL ITEM SALES", f"₹{summary['total_item_sales']:,.2f}", True),
        ]

        headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Item ID", ALIGN_CENTER, 12),
            ("Item Name", ALIGN_LEFT, 26),
            ("Category", ALIGN_LEFT, 18),
            ("Food Type", ALIGN_CENTER, 14),
            ("Unit Price (₹)", ALIGN_RIGHT, 14),
            ("Quantity Sold", ALIGN_RIGHT, 14),
            ("Sales Amount (₹)", ALIGN_RIGHT, 18),
            ("Sales Share %", ALIGN_RIGHT, 14),
        ]

        summary_rows = []
        tot_qty = sum(r["sold_quantity"] for r in rows)
        tot_amt = sum(r["sales_amount"] for r in rows)

        for r in rows:
            summary_rows.append(
                [
                    (r["sr_no"], ALIGN_CENTER, None),
                    (r["branch_id"], ALIGN_CENTER, None),
                    (r["branch_name"], ALIGN_LEFT, None),
                    (r["id"], ALIGN_CENTER, None),
                    (r["name"], ALIGN_LEFT, None),
                    (r["category"], ALIGN_LEFT, None),
                    (r["food_type"], ALIGN_CENTER, None),
                    (r["unit_price"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (r["sold_quantity"], ALIGN_RIGHT, NUM_FMT_QTY),
                    (r["sales_amount"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (f"{r['percentage_of_total']:.2f}%", ALIGN_RIGHT, None),
                ]
            )

        builder.add_summary_sheet(
            sheet_title="Item Sales Summary",
            kpis=kpis,
            headers=headers,
            data_rows=summary_rows,
            totals_row={9: (tot_qty, NUM_FMT_QTY), 10: (tot_amt, NUM_FMT_CURRENCY)},
            empty_message="No item sales recorded for the selected period.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Item_Sales_Report_{branch_tag}_{scope['date_from'].strftime('%Y%m%d')}_{scope['date_to'].strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
