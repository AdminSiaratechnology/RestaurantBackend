# app/reports/category/service.py

import io
from datetime import date, datetime
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.reports.category.queries import (
    query_categories_with_item_counts,
    query_category_sales_aggregations,
    query_category_items_detail,
)


class CategoryReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return CategoryReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        # 1. Fetch categories with item counts
        cat_rows = await query_categories_with_item_counts(db=db, branch_ids=branch_ids, search_query=search)

        # 2. Fetch sales per category for the date period
        sales_rows = await query_category_sales_aggregations(db=db, branch_ids=branch_ids, start_dt=start_dt, end_dt=end_dt)
        sales_map = {row.category_id: (safe_float(row.sold_qty), safe_float(row.sold_amount)) for row in sales_rows}

        tot_categories = len(cat_rows)
        tot_menu_items = sum(safe_int(r.item_count) for r in cat_rows)
        tot_active_items = sum(safe_int(r.active_items) for r in cat_rows)
        tot_category_sales = sum(sales_map.get(r.id, (0.0, 0.0))[1] for r in cat_rows)

        # Identify Top Category by Sales Amount
        top_cat_name = "None"
        max_cat_sales = -1.0
        for r in cat_rows:
            c_sales = sales_map.get(r.id, (0.0, 0.0))[1]
            if c_sales > max_cat_sales and c_sales > 0:
                max_cat_sales = c_sales
                top_cat_name = r.name

        if top_cat_name == "None" and cat_rows:
            top_cat_name = cat_rows[0].name

        summary_data = {
            "total_categories": tot_categories,
            "total_menu_items": tot_menu_items,
            "total_items": tot_menu_items,
            "active_categories": sum(1 for r in cat_rows if safe_int(r.active_items) > 0),
            "active_items": tot_active_items,
            "top_category": top_cat_name,
            "total_category_sales": round(tot_category_sales, 2),
            "total_sales": round(tot_category_sales, 2),
        }

        # 3. Chart: Category Sales Distribution (Sorted descending by sales amount)
        chart_data = []
        for r in cat_rows:
            qty, amt = sales_map.get(r.id, (0.0, 0.0))
            chart_data.append(
                {
                    "label": r.name,
                    "category_id": r.id,
                    "amount": round(amt, 2),
                    "quantity": round(qty, 2),
                }
            )
        chart_data.sort(key=lambda x: x["amount"], reverse=True)

        # Top 5 / 10 Categories Widget
        top_items = []
        for idx, item in enumerate(chart_data[:10], start=1):
            pct = round((item["amount"] / tot_category_sales) * 100, 2) if tot_category_sales > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": item["category_id"],
                    "name": item["label"],
                    "icon": DEFAULT_ITEM_EMOJIS[(idx - 1) % len(DEFAULT_ITEM_EMOJIS)],
                    "quantity": item["quantity"],
                    "amount": item["amount"],
                    "percent": pct,
                }
            )

        # 4. Detailed Rows (Paginated)
        branch_map = {b.id: b.name for b in branches}
        total_records = len(cat_rows)
        offset = max(page - 1, 0) * page_size
        paginated_cat_rows = cat_rows[offset : offset + page_size]

        rows = []
        for idx, r in enumerate(paginated_cat_rows, start=offset + 1):
            qty, amt = sales_map.get(r.id, (0.0, 0.0))
            pct = round((amt / tot_category_sales) * 100, 2) if tot_category_sales > 0 else 0.0
            rows.append(
                {
                    "sr_no": idx,
                    "id": r.id,
                    "branch_id": r.branch_id,
                    "branch_name": branch_map.get(r.branch_id, f"Branch #{r.branch_id}"),
                    "name": r.name,
                    "icon": r.icon or "🍽️",
                    "total_items": safe_int(r.item_count),
                    "active_items": safe_int(r.active_items),
                    "sold_quantity": round(qty, 2),
                    "sales_amount": round(amt, 2),
                    "percentage_of_total": pct,
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "category",
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
            "report": "category",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_categories": 0,
                "total_menu_items": 0,
                "total_items": 0,
                "active_categories": 0,
                "active_items": 0,
                "top_category": "None",
                "total_category_sales": 0.0,
                "total_sales": 0.0,
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
        search: Optional[str] = None,
    ) -> Tuple[io.BytesIO, str]:
        data = await CategoryReportService.get_report_data(
            db=db,
            client_id=client_id,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            search=search,
            page=1,
            page_size=10000,
        )
        scope = data["scope"]
        summary = data["summary"]
        rows = data["rows"]

        title = f"Category Report - {scope['branch_name']}" if not scope['is_all_branches'] else f"Category Report - {scope['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope["scope_name"],
            from_date=scope["date_from"],
            to_date=scope["date_to"],
        )

        # 1. Sheet 1: Category Summary
        kpis = [
            ("TOTAL CATEGORIES", str(summary["total_categories"]), False),
            ("TOTAL MENU ITEMS", str(summary["total_menu_items"]), False),
            ("ACTIVE CATEGORIES", str(summary["active_categories"]), False),
            ("TOP CATEGORY", summary["top_category"], False),
            ("TOTAL CATEGORY SALES", f"₹{summary['total_category_sales']:,.2f}", True),
        ]

        headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Category ID", ALIGN_CENTER, 14),
            ("Category Name", ALIGN_LEFT, 26),
            ("Total Items", ALIGN_RIGHT, 14),
            ("Active Items", ALIGN_RIGHT, 14),
            ("Sold Qty", ALIGN_RIGHT, 14),
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
                    (r["total_items"], ALIGN_RIGHT, None),
                    (r["active_items"], ALIGN_RIGHT, None),
                    (r["sold_quantity"], ALIGN_RIGHT, NUM_FMT_QTY),
                    (r["sales_amount"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (f"{r['percentage_of_total']:.2f}%", ALIGN_RIGHT, None),
                ]
            )

        builder.add_summary_sheet(
            sheet_title="Category Summary",
            kpis=kpis,
            headers=headers,
            data_rows=summary_rows,
            totals_row={8: (tot_qty, NUM_FMT_QTY), 9: (tot_amt, NUM_FMT_CURRENCY)},
            empty_message="No categories found for the selected branch/client.",
        )

        # 2. Sheet 2: Category Items Detail Breakdown
        client, branches, scope_meta = await validate_and_get_scope(db=db, client_id=client_id, branch_id=branch_id)
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        items_breakdown = await query_category_items_detail(db=db, branch_ids=scope_meta["branch_ids"], start_dt=start_dt, end_dt=end_dt)

        detail_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Category", ALIGN_LEFT, 22),
            ("Item ID", ALIGN_CENTER, 12),
            ("Item Name", ALIGN_LEFT, 26),
            ("Food Type", ALIGN_CENTER, 14),
            ("Sold Qty", ALIGN_RIGHT, 14),
            ("Avg Unit Price (₹)", ALIGN_RIGHT, 16),
            ("Total Sales (₹)", ALIGN_RIGHT, 18),
        ]

        detail_rows = []
        tot_d_qty = 0.0
        tot_d_amt = 0.0

        for idx, item in enumerate(items_breakdown, start=1):
            q = safe_float(item.qty_sold)
            rev = safe_float(item.revenue)
            u_p = safe_float(item.avg_unit_price)
            f_type = item.food_type.value if hasattr(item.food_type, "value") else str(item.food_type or "Veg")

            tot_d_qty += q
            tot_d_amt += rev

            detail_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (item.category_name, ALIGN_LEFT, None),
                    (item.item_id, ALIGN_CENTER, None),
                    (item.item_name, ALIGN_LEFT, None),
                    (f_type.title(), ALIGN_CENTER, None),
                    (q, ALIGN_RIGHT, NUM_FMT_QTY),
                    (u_p, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (rev, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                ]
            )

        builder.add_details_sheet(
            sheet_title="Category Items Breakdown",
            details_header_title="🍽️  CATEGORY DISHES & SALES BREAKDOWN",
            headers=detail_headers,
            data_rows=detail_rows,
            totals_row={6: (tot_d_qty, NUM_FMT_QTY), 8: (tot_d_amt, NUM_FMT_CURRENCY)},
            empty_message="No dish sales recorded in these categories.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Category_Report_{branch_tag}_{scope['date_from'].strftime('%Y%m%d')}_{scope['date_to'].strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
