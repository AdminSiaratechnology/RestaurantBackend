# app/reports/purchase/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.purchase.model import PurchaseEntry, PurchaseEntryItem
from app.accounts.vendor.model import Vendor
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
from app.utils.currency_formatter import (
    format_currency,
    get_excel_currency_num_format,
    get_branch_currency_settings_from_db,
)


class PurchaseReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        supplier_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return PurchaseReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        # Base Conditions
        conditions = [
            PurchaseEntry.branch_id.in_(branch_ids),
            PurchaseEntry.invoice_date >= f_date,
            PurchaseEntry.invoice_date <= t_date,
        ]

        if supplier_id is not None:
            conditions.append(PurchaseEntry.supplier_id == supplier_id)

        # 1. Summary Aggregations
        summary_query = select(
            func.count(PurchaseEntry.id).label("total_entries"),
            func.coalesce(func.sum(PurchaseEntry.subtotal), 0).label("total_subtotal"),
            func.coalesce(func.sum(PurchaseEntry.discount_amount), 0).label("total_discount"),
            func.coalesce(func.sum(PurchaseEntry.tax_amount), 0).label("total_tax"),
            func.coalesce(func.sum(PurchaseEntry.grand_total), 0).label("total_amount"),
        ).where(*conditions)

        summary_res = await db.execute(summary_query)
        s_row = summary_res.one()

        summary_data = {
            "total_entries": safe_int(s_row.total_entries),
            "total_subtotal": round(safe_float(s_row.total_subtotal), 2),
            "total_discount": round(safe_float(s_row.total_discount), 2),
            "total_tax": round(safe_float(s_row.total_tax), 2),
            "total_amount": round(safe_float(s_row.total_amount), 2),
            "total_purchase": round(safe_float(s_row.total_amount), 2),
        }

        # 2. Charts (7d, Month, Today, Custom)
        today = date.today()
        seven_days_ago = today - timedelta(days=6)
        month_start = today.replace(day=1)

        # 7-Days Chart
        c_7d_query = (
            select(
                PurchaseEntry.invoice_date.label("p_date"),
                func.coalesce(func.sum(PurchaseEntry.grand_total), 0).label("amount"),
                func.count(PurchaseEntry.id).label("entries"),
            )
            .where(
                PurchaseEntry.branch_id.in_(branch_ids),
                PurchaseEntry.invoice_date >= seven_days_ago,
                PurchaseEntry.invoice_date <= today,
                *( [PurchaseEntry.supplier_id == supplier_id] if supplier_id else [] )
            )
            .group_by(PurchaseEntry.invoice_date)
        )
        c_7d_res = await db.execute(c_7d_query)
        c_7d_map = {str(row.p_date): (safe_float(row.amount), safe_int(row.entries)) for row in c_7d_res}

        chart_7d = []
        for i in range(7):
            curr = seven_days_ago + timedelta(days=i)
            curr_str = str(curr)
            amt, ent = c_7d_map.get(curr_str, (0.0, 0))
            lbl = "Today" if curr == today else ("Yesterday" if curr == today - timedelta(days=1) else f"{(today - curr).days} Days Ago")
            chart_7d.append({"date": curr_str, "label": lbl, "amount": round(amt, 2), "quantity": ent})

        # Month Chart (Weekly Breakdown)
        weeks_def = [
            ("Week 1", 1, 7),
            ("Week 2", 8, 14),
            ("Week 3", 15, 21),
            ("Week 4", 22, 28),
            ("Week 5", 29, 31),
        ]
        c_m_query = (
            select(
                func.extract("day", PurchaseEntry.invoice_date).label("day"),
                func.coalesce(func.sum(PurchaseEntry.grand_total), 0).label("amount"),
            )
            .where(
                PurchaseEntry.branch_id.in_(branch_ids),
                PurchaseEntry.invoice_date >= month_start,
                PurchaseEntry.invoice_date <= today,
                *( [PurchaseEntry.supplier_id == supplier_id] if supplier_id else [] )
            )
            .group_by(func.extract("day", PurchaseEntry.invoice_date))
        )
        c_m_res = await db.execute(c_m_query)
        day_map = {int(row.day): safe_float(row.amount) for row in c_m_res}

        chart_month = []
        for w_label, start_d, end_d in weeks_def:
            w_sum = sum(day_map.get(d, 0.0) for d in range(start_d, end_d + 1))
            chart_month.append({"label": w_label, "amount": round(w_sum, 2), "quantity": 0.0})

        # Today Chart (Time Interval Breakdown)
        time_slots = [
            ("9 AM", 0, 9),
            ("12 PM", 9, 12),
            ("3 PM", 12, 15),
            ("6 PM", 15, 18),
            ("9 PM", 18, 21),
            ("11 PM", 21, 24),
        ]
        c_t_query = (
            select(
                func.extract("hour", PurchaseEntry.created_at).label("hour"),
                func.coalesce(func.sum(PurchaseEntry.grand_total), 0).label("amount"),
            )
            .where(
                PurchaseEntry.branch_id.in_(branch_ids),
                PurchaseEntry.invoice_date == today,
                *( [PurchaseEntry.supplier_id == supplier_id] if supplier_id else [] )
            )
            .group_by(func.extract("hour", PurchaseEntry.created_at))
        )
        c_t_res = await db.execute(c_t_query)
        hour_map = {int(row.hour): safe_float(row.amount) for row in c_t_res}

        chart_today = []
        for slot_lbl, h_s, h_e in time_slots:
            slot_amt = sum(hour_map.get(h, 0.0) for h in range(h_s, h_e))
            chart_today.append({"label": slot_lbl, "amount": round(slot_amt, 2), "quantity": 0.0})

        # Active Chart
        if time_range == "today":
            active_chart = chart_today
        elif time_range in ("month", "this_month"):
            active_chart = chart_month
        elif time_range in ("7d", "last_7_days"):
            active_chart = chart_7d
        else:
            c_custom_query = (
                select(
                    PurchaseEntry.invoice_date.label("p_date"),
                    func.coalesce(func.sum(PurchaseEntry.grand_total), 0).label("amount"),
                    func.count(PurchaseEntry.id).label("entries"),
                )
                .where(*conditions)
                .group_by(PurchaseEntry.invoice_date)
                .order_by(PurchaseEntry.invoice_date.asc())
            )
            c_custom_res = await db.execute(c_custom_query)
            active_chart = [
                {
                    "date": str(row.p_date),
                    "label": row.p_date.strftime("%d-%m"),
                    "amount": round(safe_float(row.amount), 2),
                    "quantity": safe_int(row.entries),
                }
                for row in c_custom_res
            ]

        # 3. Top Purchasing Items
        top_items_query = (
            select(
                PurchaseEntryItem.inventory_item_id,
                PurchaseEntryItem.item_name,
                func.sum(PurchaseEntryItem.quantity).label("total_quantity"),
                func.sum(PurchaseEntryItem.amount).label("total_amount"),
            )
            .join(PurchaseEntry, PurchaseEntry.id == PurchaseEntryItem.purchase_entry_id)
            .where(*conditions)
            .group_by(PurchaseEntryItem.inventory_item_id, PurchaseEntryItem.item_name)
            .order_by(func.sum(PurchaseEntryItem.amount).desc())
            .limit(10)
        )
        top_items_res = await db.execute(top_items_query)
        top_rows = top_items_res.all()
        total_top_amount = sum(safe_float(r.total_amount) for r in top_rows)

        top_items = []
        for idx, item in enumerate(top_rows, start=1):
            amt = safe_float(item.total_amount)
            pct = round((amt / total_top_amount) * 100, 2) if total_top_amount > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": item.inventory_item_id,
                    "name": item.item_name or "Unnamed Item",
                    "icon": DEFAULT_ITEM_EMOJIS[(idx - 1) % len(DEFAULT_ITEM_EMOJIS)],
                    "quantity": round(safe_float(item.total_quantity), 2),
                    "amount": round(amt, 2),
                    "percent": pct,
                }
            )

        # 4. Detailed Data Rows (Paginated)
        total_records_res = await db.execute(select(func.count(PurchaseEntry.id)).where(*conditions))
        total_records = total_records_res.scalar() or 0

        offset = max(page - 1, 0) * page_size
        purchases_query = (
            select(PurchaseEntry)
            .options(
                joinedload(PurchaseEntry.branch),
                joinedload(PurchaseEntry.supplier),
                selectinload(PurchaseEntry.items),
            )
            .where(*conditions)
            .order_by(PurchaseEntry.invoice_date.desc(), PurchaseEntry.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        purchases_res = await db.execute(purchases_query)
        purchases = purchases_res.scalars().all()

        rows = []
        for idx, p in enumerate(purchases, start=offset + 1):
            b_name = p.branch.name if p.branch else f"Branch #{p.branch_id}"
            supp_name = (
                p.supplier.vendor_name or p.supplier.name
                if p.supplier
                else (f"Supplier #{p.supplier_id}" if p.supplier_id else "—")
            )
            inv_date_str = p.invoice_date.strftime("%d-%m-%Y") if p.invoice_date else "—"

            rows.append(
                {
                    "sr_no": idx,
                    "id": p.id,
                    "branch_id": p.branch_id,
                    "branch_name": b_name,
                    "invoice_number": p.invoice_number or f"INV-{p.id}",
                    "invoice_date": inv_date_str,
                    "supplier_id": p.supplier_id,
                    "supplier_name": supp_name,
                    "supplier_invoice_number": p.supplier_invoice_number or "—",
                    "payment_terms": p.payment_terms or "—",
                    "subtotal": round(safe_float(p.subtotal), 2),
                    "discount": round(safe_float(p.discount_amount), 2),
                    "tax": round(safe_float(p.tax_amount), 2),
                    "grand_total": round(safe_float(p.grand_total), 2),
                    "items_count": len(p.items) if p.items else 0,
                    "notes": p.notes or "",
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "purchase",
            "scope": {
                **scope_meta,
                "date_from": f_date,
                "date_to": t_date,
            },
            "summary": summary_data,
            "chart": active_chart,
            "charts": {
                "7d": chart_7d,
                "month": chart_month,
                "today": chart_today,
            },
            "top_items": top_items,
            "top_purchasing_items": [
                {
                    "rank": it["rank"],
                    "inventory_item_id": it["id"],
                    "item_name": it["name"],
                    "total_quantity": it["quantity"],
                    "total_amount": it["amount"],
                    "percentage_of_total": it["percent"],
                }
                for it in top_items
            ],
            "rows": rows,
            "kpis": {
                "today_purchase": chart_today[3]["amount"] if len(chart_today) > 3 else summary_data["total_amount"],
                "last_7_days_purchase": sum(c["amount"] for c in chart_7d),
                "current_month_purchase": sum(c["amount"] for c in chart_month),
                "total_purchase_entries": summary_data["total_entries"],
            },
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
            "report": "purchase",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_entries": 0,
                "total_subtotal": 0.0,
                "total_discount": 0.0,
                "total_tax": 0.0,
                "total_amount": 0.0,
                "total_purchase": 0.0,
            },
            "chart": [],
            "charts": {"7d": [], "month": [], "today": []},
            "top_items": [],
            "top_purchasing_items": [],
            "rows": [],
            "kpis": {
                "today_purchase": 0.0,
                "last_7_days_purchase": 0.0,
                "current_month_purchase": 0.0,
                "total_purchase_entries": 0,
            },
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
        supplier_id: Optional[int] = None,
    ) -> Tuple[io.BytesIO, str]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        conditions = [
            PurchaseEntry.branch_id.in_(branch_ids),
            PurchaseEntry.invoice_date >= f_date,
            PurchaseEntry.invoice_date <= t_date,
        ]

        supplier_name = None
        if supplier_id is not None:
            conditions.append(PurchaseEntry.supplier_id == supplier_id)
            vend_res = await db.execute(select(Vendor).where(Vendor.id == supplier_id))
            vend = vend_res.scalar_one_or_none()
            if vend:
                supplier_name = vend.vendor_name or vend.name

        purchases_res = await db.execute(
            select(PurchaseEntry)
            .options(
                joinedload(PurchaseEntry.branch),
                joinedload(PurchaseEntry.supplier),
                selectinload(PurchaseEntry.items),
            )
            .where(*conditions)
            .order_by(PurchaseEntry.invoice_date.desc(), PurchaseEntry.id.desc())
        )
        purchases = purchases_res.scalars().all()

        tot_entries = len(purchases)
        tot_subtotal = sum(safe_float(p.subtotal) for p in purchases)
        tot_discount = sum(safe_float(p.discount_amount) for p in purchases)
        tot_tax = sum(safe_float(p.tax_amount) for p in purchases)
        tot_amount = sum(safe_float(p.grand_total) for p in purchases)

        title = f"Purchase Report - {scope_meta['branch_name']}" if not scope_meta['is_all_branches'] else f"Purchase Report - {scope_meta['client_name'] or 'All Branches'}"
        supp_extra = f" | Supplier: {supplier_name}" if supplier_name else ""
        curr_code, curr_symbol, dec_places = await get_branch_currency_settings_from_db(branch_id, db)
        num_fmt_curr = get_excel_currency_num_format(currency_symbol=curr_symbol, decimal_places=dec_places)

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope_meta["scope_name"],
            from_date=f_date,
            to_date=t_date,
            filter_subtitle_extra=supp_extra,
        )

        # 1. Sheet 1: Purchase Summary
        kpis = [
            ("TOTAL ENTRIES", str(tot_entries), False),
            ("TOTAL SUBTOTAL", format_currency(tot_subtotal, currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL DISCOUNT", format_currency(tot_discount, currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL TAX", format_currency(tot_tax, currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL PURCHASE AMOUNT", format_currency(tot_amount, currency_symbol=curr_symbol, decimal_places=dec_places), True),
        ]

        summary_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Purchase ID", ALIGN_CENTER, 14),
            ("Invoice Number", ALIGN_LEFT, 18),
            ("Invoice Date", ALIGN_CENTER, 14),
            ("Supplier ID", ALIGN_CENTER, 12),
            ("Supplier Name", ALIGN_LEFT, 24),
            ("Supplier Inv No", ALIGN_LEFT, 18),
            ("Supplier Inv Date", ALIGN_CENTER, 16),
            ("Delivery Date", ALIGN_CENTER, 14),
            ("Reference No", ALIGN_LEFT, 16),
            ("Payment Terms", ALIGN_LEFT, 16),
            ("Due Date", ALIGN_CENTER, 14),
            (f"Subtotal ({curr_symbol})", ALIGN_RIGHT, 16),
            (f"Discount ({curr_symbol})", ALIGN_RIGHT, 14),
            (f"Tax ({curr_symbol})", ALIGN_RIGHT, 14),
            (f"Total Amount ({curr_symbol})", ALIGN_RIGHT, 18),
            ("Notes", ALIGN_LEFT, 26),
        ]

        summary_rows = []
        for idx, p in enumerate(purchases, start=1):
            b_name = p.branch.name if p.branch else f"Branch #{p.branch_id}"
            s_name = (
                p.supplier.vendor_name or p.supplier.name
                if p.supplier
                else f"Supplier #{p.supplier_id}"
            )
            inv_d = p.invoice_date.strftime("%d-%m-%Y") if p.invoice_date else "—"
            supp_inv_d = p.supplier_invoice_date.strftime("%d-%m-%Y") if p.supplier_invoice_date else "—"
            deliv_d = p.delivery_date.strftime("%d-%m-%Y") if p.delivery_date else "—"
            due_d = p.due_date.strftime("%d-%m-%Y") if p.due_date else "—"

            summary_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (p.branch_id, ALIGN_CENTER, None),
                    (b_name, ALIGN_LEFT, None),
                    (p.id, ALIGN_CENTER, None),
                    (p.invoice_number or f"INV-{p.id}", ALIGN_LEFT, None),
                    (inv_d, ALIGN_CENTER, None),
                    (p.supplier_id or "—", ALIGN_CENTER, None),
                    (s_name, ALIGN_LEFT, None),
                    (p.supplier_invoice_number or "—", ALIGN_LEFT, None),
                    (supp_inv_d, ALIGN_CENTER, None),
                    (deliv_d, ALIGN_CENTER, None),
                    (p.reference_number or "—", ALIGN_LEFT, None),
                    (p.payment_terms or "—", ALIGN_LEFT, None),
                    (due_d, ALIGN_CENTER, None),
                    (safe_float(p.subtotal), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(p.discount_amount), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(p.tax_amount), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(p.grand_total), ALIGN_RIGHT, num_fmt_curr),
                    (p.notes or "", ALIGN_LEFT, None),
                ]
            )

        summary_totals = {
            15: (tot_subtotal, num_fmt_curr),
            16: (tot_discount, num_fmt_curr),
            17: (tot_tax, num_fmt_curr),
            18: (tot_amount, num_fmt_curr),
        }

        builder.add_summary_sheet(
            sheet_title="Purchase Summary",
            kpis=kpis,
            headers=summary_headers,
            data_rows=summary_rows,
            totals_row=summary_totals,
            empty_message="No purchase entries found for the selected filters.",
        )

        # 2. Sheet 2: Purchase Items Detail
        detail_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Purchase ID", ALIGN_CENTER, 14),
            ("Invoice Number", ALIGN_LEFT, 18),
            ("Invoice Date", ALIGN_CENTER, 14),
            ("Supplier Name", ALIGN_LEFT, 24),
            ("Item Name", ALIGN_LEFT, 26),
            ("Inventory Item ID", ALIGN_CENTER, 16),
            ("Category", ALIGN_LEFT, 16),
            ("Godown ID", ALIGN_CENTER, 12),
            ("Base Unit", ALIGN_CENTER, 12),
            ("Display Unit", ALIGN_CENTER, 14),
            ("Conversion Factor", ALIGN_RIGHT, 16),
            ("Quantity", ALIGN_RIGHT, 14),
            (f"Rate ({curr_symbol})", ALIGN_RIGHT, 14),
            ("Discount %", ALIGN_RIGHT, 14),
            ("Tax %", ALIGN_RIGHT, 12),
            (f"Item Total ({curr_symbol})", ALIGN_RIGHT, 18),
        ]

        detail_rows = []
        item_counter = 1
        total_item_qty = 0.0
        total_item_amount = 0.0

        for p in purchases:
            b_name = p.branch.name if p.branch else f"Branch #{p.branch_id}"
            s_name = (
                p.supplier.vendor_name or p.supplier.name
                if p.supplier
                else f"Supplier #{p.supplier_id}"
            )
            inv_no = p.invoice_number or f"INV-{p.id}"
            inv_dt = p.invoice_date.strftime("%d-%m-%Y") if p.invoice_date else "—"

            if p.items:
                for item in p.items:
                    qty = safe_float(item.quantity)
                    rate = safe_float(item.rate)
                    disc_pct = safe_float(item.discount_percent)
                    tax_pct = safe_float(item.tax_percent)
                    amt = safe_float(item.amount or (qty * rate))
                    conv_factor = safe_float(item.conversion_factor or 1.0)

                    total_item_qty += qty
                    total_item_amount += amt

                    detail_rows.append(
                        [
                            (item_counter, ALIGN_CENTER, None),
                            (p.branch_id, ALIGN_CENTER, None),
                            (b_name, ALIGN_LEFT, None),
                            (p.id, ALIGN_CENTER, None),
                            (inv_no, ALIGN_LEFT, None),
                            (inv_dt, ALIGN_CENTER, None),
                            (s_name, ALIGN_LEFT, None),
                            (item.item_name or "Unnamed Item", ALIGN_LEFT, None),
                            (item.inventory_item_id or "—", ALIGN_CENTER, None),
                            (item.row_category or "—", ALIGN_LEFT, None),
                            (item.godown_id or "—", ALIGN_CENTER, None),
                            (item.unit or "—", ALIGN_CENTER, None),
                            (item.display_unit or "—", ALIGN_CENTER, None),
                            (conv_factor, ALIGN_RIGHT, NUM_FMT_QTY),
                            (qty, ALIGN_RIGHT, NUM_FMT_QTY),
                            (rate, ALIGN_RIGHT, num_fmt_curr),
                            (disc_pct, ALIGN_RIGHT, NUM_FMT_QTY),
                            (tax_pct, ALIGN_RIGHT, NUM_FMT_QTY),
                            (amt, ALIGN_RIGHT, num_fmt_curr),
                        ]
                    )
                    item_counter += 1

        detail_totals = {
            15: (total_item_qty, NUM_FMT_QTY),
            19: (total_item_amount, num_fmt_curr),
        }

        builder.add_details_sheet(
            sheet_title="Purchase Items",
            details_header_title="📦  PURCHASE ITEMS DETAIL",
            headers=detail_headers,
            data_rows=detail_rows,
            totals_row=detail_totals,
            empty_message="No purchase items recorded for the selected period.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Purchase_Report_{branch_tag}_{f_date.strftime('%Y%m%d')}_{t_date.strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
