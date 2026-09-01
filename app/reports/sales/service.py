# app/reports/sales/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.order.model import Order, OrderItem
from app.accounts.item.model import Item
from app.accounts.category.model import Category
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


class SalesReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        payment_method: Optional[str] = None,
        order_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return SalesReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        # Base Conditions
        conditions = [
            Bill.branch_id.in_(branch_ids),
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
            Bill.payment_status == PaymentStatus.complete,
        ]

        if payment_method:
            conditions.append(Bill.payment_method.ilike(f"%{payment_method}%"))
        if order_type:
            conditions.append(Bill.order_type.ilike(f"%{order_type}%"))

        # 1. Summary Aggregations
        summary_query = select(
            func.count(Bill.id).label("total_orders"),
            func.coalesce(func.sum(Bill.subtotal), 0).label("total_subtotal"),
            func.coalesce(
                func.sum(Bill.discount_amount + Bill.offer_discount + Bill.wallet_discount), 0
            ).label("total_discount"),
            func.coalesce(
                func.sum(Bill.tax_total + Bill.service_charge_amount), 0
            ).label("total_tax"),
            func.coalesce(func.sum(Bill.final_amount), 0).label("total_sales"),
            func.coalesce(func.sum(Bill.paid_amount), 0).label("total_paid"),
            func.coalesce(func.sum(Bill.due_amount), 0).label("total_due"),
        ).where(*conditions)

        summary_res = await db.execute(summary_query)
        s_row = summary_res.one()

        summary_data = {
            "total_orders": safe_int(s_row.total_orders),
            "total_subtotal": round(safe_float(s_row.total_subtotal), 2),
            "total_discount": round(safe_float(s_row.total_discount), 2),
            "total_tax": round(safe_float(s_row.total_tax), 2),
            "total_sales": round(safe_float(s_row.total_sales), 2),
            "total_paid": round(safe_float(s_row.total_paid), 2),
            "total_due": round(safe_float(s_row.total_due), 2),
            "average_order_value": (
                round(safe_float(s_row.total_sales) / max(safe_int(s_row.total_orders), 1), 2)
                if safe_int(s_row.total_orders) > 0
                else 0.0
            ),
        }

        # 2. Charts (7d, Month, Today, Custom)
        today = date.today()
        seven_days_ago = today - timedelta(days=6)
        month_start = today.replace(day=1)

        # 7-Days Chart
        c_7d_query = (
            select(
                func.date(Bill.created_at).label("bill_date"),
                func.coalesce(func.sum(Bill.final_amount), 0).label("amount"),
                func.count(Bill.id).label("orders"),
            )
            .where(
                Bill.branch_id.in_(branch_ids),
                Bill.created_at >= datetime.combine(seven_days_ago, datetime.min.time()),
                Bill.created_at <= datetime.combine(today, datetime.max.time()),
                Bill.payment_status == PaymentStatus.complete,
            )
            .group_by(func.date(Bill.created_at))
        )
        c_7d_res = await db.execute(c_7d_query)
        c_7d_map = {str(row.bill_date): (safe_float(row.amount), safe_int(row.orders)) for row in c_7d_res}

        chart_7d = []
        for i in range(7):
            curr = seven_days_ago + timedelta(days=i)
            curr_str = str(curr)
            amt, ords = c_7d_map.get(curr_str, (0.0, 0))
            lbl = "Today" if curr == today else ("Yesterday" if curr == today - timedelta(days=1) else curr.strftime("%d-%m"))
            chart_7d.append({"date": curr_str, "label": lbl, "amount": round(amt, 2), "quantity": ords})

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
                func.extract("day", Bill.created_at).label("day"),
                func.coalesce(func.sum(Bill.final_amount), 0).label("amount"),
            )
            .where(
                Bill.branch_id.in_(branch_ids),
                Bill.created_at >= datetime.combine(month_start, datetime.min.time()),
                Bill.created_at <= datetime.combine(today, datetime.max.time()),
                Bill.payment_status == PaymentStatus.complete,
            )
            .group_by(func.extract("day", Bill.created_at))
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
                func.extract("hour", Bill.created_at).label("hour"),
                func.coalesce(func.sum(Bill.final_amount), 0).label("amount"),
            )
            .where(
                Bill.branch_id.in_(branch_ids),
                Bill.created_at >= datetime.combine(today, datetime.min.time()),
                Bill.created_at <= datetime.combine(today, datetime.max.time()),
                Bill.payment_status == PaymentStatus.complete,
            )
            .group_by(func.extract("hour", Bill.created_at))
        )
        c_t_res = await db.execute(c_t_query)
        hour_map = {int(row.hour): safe_float(row.amount) for row in c_t_res}

        chart_today = []
        for slot_lbl, h_s, h_e in time_slots:
            slot_amt = sum(hour_map.get(h, 0.0) for h in range(h_s, h_e))
            chart_today.append({"label": slot_lbl, "amount": round(slot_amt, 2), "quantity": 0.0})

        # Active Chart according to selected time range
        if time_range == "today":
            active_chart = chart_today
        elif time_range in ("month", "this_month"):
            active_chart = chart_month
        elif time_range in ("7d", "last_7_days"):
            active_chart = chart_7d
        else:
            # Custom range daily breakdown
            c_custom_query = (
                select(
                    func.date(Bill.created_at).label("bill_date"),
                    func.coalesce(func.sum(Bill.final_amount), 0).label("amount"),
                    func.count(Bill.id).label("orders"),
                )
                .where(*conditions)
                .group_by(func.date(Bill.created_at))
                .order_by(func.date(Bill.created_at).asc())
            )
            c_custom_res = await db.execute(c_custom_query)
            active_chart = [
                {
                    "date": str(row.bill_date),
                    "label": row.bill_date.strftime("%d-%m"),
                    "amount": round(safe_float(row.amount), 2),
                    "quantity": safe_int(row.orders),
                }
                for row in c_custom_res
            ]

        # 3. Top Selling Items
        top_items_query = (
            select(
                OrderItem.item_id,
                Item.name.label("item_name"),
                func.sum(OrderItem.quantity).label("total_quantity"),
                func.sum(OrderItem.total_price).label("total_amount"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(Item, Item.id == OrderItem.item_id)
            .where(
                Order.branch_id.in_(branch_ids),
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
            )
            .group_by(OrderItem.item_id, Item.name)
            .order_by(func.sum(OrderItem.total_price).desc())
            .limit(10)
        )
        top_items_res = await db.execute(top_items_query)
        top_rows = top_items_res.all()
        total_top_sales = sum(safe_float(r.total_amount) for r in top_rows)

        top_items = []
        for idx, item in enumerate(top_rows, start=1):
            amt = safe_float(item.total_amount)
            pct = round((amt / total_top_sales) * 100, 2) if total_top_sales > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": item.item_id,
                    "name": item.item_name,
                    "icon": DEFAULT_ITEM_EMOJIS[(idx - 1) % len(DEFAULT_ITEM_EMOJIS)],
                    "quantity": round(safe_float(item.total_quantity), 2),
                    "amount": round(amt, 2),
                    "percent": pct,
                }
            )

        # 4. Detailed Data Rows (Paginated)
        total_records_res = await db.execute(select(func.count(Bill.id)).where(*conditions))
        total_records = total_records_res.scalar() or 0

        offset = max(page - 1, 0) * page_size
        bills_query = (
            select(Bill)
            .options(joinedload(Bill.branch), joinedload(Bill.customer))
            .where(*conditions)
            .order_by(Bill.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        bills_res = await db.execute(bills_query)
        bills = bills_res.scalars().all()

        rows = []
        for idx, b in enumerate(bills, start=offset + 1):
            b_name = b.branch.name if b.branch else f"Branch #{b.branch_id}"
            cust_name = b.customer_name or (b.customer.name if b.customer else "Walk-in Customer")
            inv_date_str = b.created_at.strftime("%d-%m-%Y %H:%M") if b.created_at else "—"
            rows.append(
                {
                    "sr_no": idx,
                    "id": b.id,
                    "branch_id": b.branch_id,
                    "branch_name": b_name,
                    "invoice_no": b.invoice_no,
                    "invoice_date": inv_date_str,
                    "customer_name": cust_name,
                    "customer_phone": b.customer_phone or "—",
                    "order_type": (b.order_type or "Dine-in").title(),
                    "payment_status": str(b.payment_status.value if hasattr(b.payment_status, "value") else b.payment_status).title(),
                    "payment_method": (b.payment_method or "Cash").upper(),
                    "subtotal": round(safe_float(b.subtotal), 2),
                    "discount": round(safe_float(b.discount_amount + b.offer_discount + b.wallet_discount), 2),
                    "tax": round(safe_float(b.tax_total + b.service_charge_amount), 2),
                    "grand_total": round(safe_float(b.grand_total), 2),
                    "final_amount": round(safe_float(b.final_amount), 2),
                    "paid_amount": round(safe_float(b.paid_amount), 2),
                    "due_amount": round(safe_float(b.due_amount), 2),
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "sales",
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
            "report": "sales",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_orders": 0,
                "total_subtotal": 0.0,
                "total_discount": 0.0,
                "total_tax": 0.0,
                "total_sales": 0.0,
                "total_paid": 0.0,
                "total_due": 0.0,
                "average_order_value": 0.0,
            },
            "chart": [],
            "charts": {"7d": [], "month": [], "today": []},
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
        payment_method: Optional[str] = None,
        order_type: Optional[str] = None,
    ) -> Tuple[io.BytesIO, str]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        conditions = [
            Bill.branch_id.in_(branch_ids),
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
            Bill.payment_status == PaymentStatus.complete,
        ]

        if payment_method:
            conditions.append(Bill.payment_method.ilike(f"%{payment_method}%"))
        if order_type:
            conditions.append(Bill.order_type.ilike(f"%{order_type}%"))

        # Query all bills matching criteria
        bills_res = await db.execute(
            select(Bill)
            .options(
                joinedload(Bill.branch),
                joinedload(Bill.customer),
                joinedload(Bill.order).selectinload(Order.order_items).joinedload(OrderItem.item).joinedload(Item.category),
            )
            .where(*conditions)
            .order_by(Bill.created_at.desc())
        )
        bills = bills_res.scalars().all()

        # Compute totals
        tot_orders = len(bills)
        tot_subtotal = sum(safe_float(b.subtotal) for b in bills)
        tot_discount = sum(safe_float(b.discount_amount + b.offer_discount + b.wallet_discount) for b in bills)
        tot_tax = sum(safe_float(b.tax_total + b.service_charge_amount) for b in bills)
        tot_sales = sum(safe_float(b.final_amount) for b in bills)
        tot_paid = sum(safe_float(b.paid_amount) for b in bills)
        tot_due = sum(safe_float(b.due_amount) for b in bills)

        curr_code, curr_symbol, dec_places = await get_branch_currency_settings_from_db(branch_id, db)
        num_fmt_curr = get_excel_currency_num_format(currency_symbol=curr_symbol, decimal_places=dec_places)

        title = f"Sales Report - {scope_meta['branch_name']}" if not scope_meta['is_all_branches'] else f"Sales Report - {scope_meta['client_name'] or 'All Branches'}"
        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope_meta["scope_name"],
            from_date=f_date,
            to_date=t_date,
        )

        # 1. Sheet 1: Sales Summary
        kpis = [
            ("TOTAL ORDERS", str(tot_orders), False),
            ("TOTAL SUBTOTAL", format_currency(tot_subtotal, currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL DISCOUNT", format_currency(tot_discount, currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL TAX", format_currency(tot_tax, currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL SALES AMOUNT", format_currency(tot_sales, currency_symbol=curr_symbol, decimal_places=dec_places), True),
        ]

        summary_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Invoice No", ALIGN_LEFT, 18),
            ("Invoice Date", ALIGN_CENTER, 18),
            ("Customer Name", ALIGN_LEFT, 22),
            ("Customer Phone", ALIGN_CENTER, 16),
            ("Order Type", ALIGN_CENTER, 14),
            ("Payment Status", ALIGN_CENTER, 14),
            ("Payment Method", ALIGN_CENTER, 16),
            (f"Subtotal ({curr_symbol})", ALIGN_RIGHT, 16),
            (f"Discount ({curr_symbol})", ALIGN_RIGHT, 14),
            (f"Tax ({curr_symbol})", ALIGN_RIGHT, 14),
            (f"Grand Total ({curr_symbol})", ALIGN_RIGHT, 16),
            (f"Final Sales ({curr_symbol})", ALIGN_RIGHT, 18),
            (f"Paid ({curr_symbol})", ALIGN_RIGHT, 16),
            (f"Due ({curr_symbol})", ALIGN_RIGHT, 14),
        ]

        summary_rows = []
        for idx, b in enumerate(bills, start=1):
            b_name = b.branch.name if b.branch else f"Branch #{b.branch_id}"
            cust_name = b.customer_name or (b.customer.name if b.customer else "Walk-in Customer")
            inv_date = b.created_at.strftime("%d-%m-%Y %H:%M") if b.created_at else "—"

            summary_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (b.branch_id, ALIGN_CENTER, None),
                    (b_name, ALIGN_LEFT, None),
                    (b.invoice_no, ALIGN_LEFT, None),
                    (inv_date, ALIGN_CENTER, None),
                    (cust_name, ALIGN_LEFT, None),
                    (b.customer_phone or "—", ALIGN_CENTER, None),
                    ((b.order_type or "Dine-in").title(), ALIGN_CENTER, None),
                    (str(b.payment_status.value if hasattr(b.payment_status, "value") else b.payment_status).title(), ALIGN_CENTER, None),
                    ((b.payment_method or "Cash").upper(), ALIGN_CENTER, None),
                    (safe_float(b.subtotal), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(b.discount_amount + b.offer_discount + b.wallet_discount), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(b.tax_total + b.service_charge_amount), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(b.grand_total), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(b.final_amount), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(b.paid_amount), ALIGN_RIGHT, num_fmt_curr),
                    (safe_float(b.due_amount), ALIGN_RIGHT, num_fmt_curr),
                ]
            )

        summary_totals = {
            11: (tot_subtotal, num_fmt_curr),
            12: (tot_discount, num_fmt_curr),
            13: (tot_tax, num_fmt_curr),
            14: (sum(safe_float(b.grand_total) for b in bills), num_fmt_curr),
            15: (tot_sales, num_fmt_curr),
            16: (tot_paid, num_fmt_curr),
            17: (tot_due, num_fmt_curr),
        }

        builder.add_summary_sheet(
            sheet_title="Sales Summary",
            kpis=kpis,
            headers=summary_headers,
            data_rows=summary_rows,
            totals_row=summary_totals,
            empty_message="No sales invoices found for the selected period.",
        )

        # 2. Sheet 2: Item-level Sales Breakdown
        detail_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Invoice No", ALIGN_LEFT, 18),
            ("Order ID", ALIGN_CENTER, 12),
            ("Date", ALIGN_CENTER, 14),
            ("Item Name", ALIGN_LEFT, 26),
            ("Category", ALIGN_LEFT, 18),
            ("Quantity", ALIGN_RIGHT, 12),
            (f"Unit Price ({curr_symbol})", ALIGN_RIGHT, 14),
            ("Discount %", ALIGN_RIGHT, 12),
            ("Tax %", ALIGN_RIGHT, 12),
            (f"Item Total ({curr_symbol})", ALIGN_RIGHT, 18),
        ]

        detail_rows = []
        item_counter = 1
        total_items_qty = 0.0
        total_items_amount = 0.0

        for b in bills:
            b_name = b.branch.name if b.branch else f"Branch #{b.branch_id}"
            inv_date = b.created_at.strftime("%d-%m-%Y") if b.created_at else "—"
            if b.order and b.order.order_items:
                for item in b.order.order_items:
                    item_name = item.item.name if item.item else f"Item #{item.item_id}"
                    cat_name = (item.item.category.name if (item.item and item.item.category) else "General")
                    qty = safe_float(item.quantity)
                    u_price = safe_float(item.unit_price)
                    disc_pct = safe_float(item.discount_percent)
                    tax_pct = safe_float(item.tax_percent)
                    tot_p = safe_float(item.total_price or (qty * u_price))

                    total_items_qty += qty
                    total_items_amount += tot_p

                    detail_rows.append(
                        [
                            (item_counter, ALIGN_CENTER, None),
                            (b_name, ALIGN_LEFT, None),
                            (b.invoice_no, ALIGN_LEFT, None),
                            (b.order_id, ALIGN_CENTER, None),
                            (inv_date, ALIGN_CENTER, None),
                            (item_name, ALIGN_LEFT, None),
                            (cat_name, ALIGN_LEFT, None),
                            (qty, ALIGN_RIGHT, NUM_FMT_QTY),
                            (u_price, ALIGN_RIGHT, num_fmt_curr),
                            (disc_pct, ALIGN_RIGHT, NUM_FMT_QTY),
                            (tax_pct, ALIGN_RIGHT, NUM_FMT_QTY),
                            (tot_p, ALIGN_RIGHT, num_fmt_curr),
                        ]
                    )
                    item_counter += 1

        detail_totals = {
            8: (total_items_qty, NUM_FMT_QTY),
            12: (total_items_amount, num_fmt_curr),
        }

        builder.add_details_sheet(
            sheet_title="Sales Items Detail",
            details_header_title="📦  SALES ITEMS BREAKDOWN",
            headers=detail_headers,
            data_rows=detail_rows,
            totals_row=detail_totals,
            empty_message="No sales items found for the selected period.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Sales_Report_{branch_tag}_{f_date.strftime('%Y%m%d')}_{t_date.strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
