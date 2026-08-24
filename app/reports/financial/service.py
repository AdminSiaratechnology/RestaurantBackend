# app/reports/financial/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.order.model import Order, OrderItem
from app.accounts.pricing.model import Pricing
from app.accounts.item.model import Item
from app.reports.constants import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    ALIGN_RIGHT,
    NUM_FMT_CURRENCY,
    NUM_FMT_QTY,
    NUM_FMT_PERCENT,
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


class FinancialReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return FinancialReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        conditions = [
            Bill.branch_id.in_(branch_ids),
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
            Bill.payment_status == PaymentStatus.complete,
        ]

        # 1. Summary Aggregations
        summary_query = select(
            func.count(Bill.id).label("paid_orders"),
            func.coalesce(func.sum(Bill.subtotal), 0).label("gross_revenue"),
            func.coalesce(
                func.sum(Bill.discount_amount + Bill.offer_discount + Bill.wallet_discount), 0
            ).label("total_discounts"),
            func.coalesce(
                func.sum(Bill.tax_total + Bill.service_charge_amount), 0
            ).label("total_tax_collected"),
            func.coalesce(func.sum(Bill.final_amount), 0).label("net_revenue"),
        ).where(*conditions)

        summary_res = await db.execute(summary_query)
        s_row = summary_res.one()

        gross_rev = safe_float(s_row.gross_revenue)
        net_rev = safe_float(s_row.net_revenue)
        tax_coll = safe_float(s_row.total_tax_collected)
        discounts = safe_float(s_row.total_discounts)
        paid_orders = safe_int(s_row.paid_orders)

        # Estimate food cost / COGS from OrderItems & Pricing
        cost_query = (
            select(
                func.coalesce(
                    func.sum(OrderItem.quantity * func.coalesce(Pricing.cost_price, 0)), 0
                )
            )
            .join(Bill, Bill.order_id == OrderItem.order_id)
            .join(Item, Item.id == OrderItem.item_id)
            .outerjoin(Pricing, Pricing.item_id == Item.id)
            .where(*conditions)
        )
        cost_res = await db.execute(cost_query)
        food_cost = safe_float(cost_res.scalar())

        # If food cost is 0 because cost_price isn't entered, estimate reasonable default (e.g. 30% of subtotal)
        gross_profit = round(net_rev - food_cost, 2)
        profit_margin = round((gross_profit / net_rev) * 100, 2) if net_rev > 0 else 0.0

        summary_data = {
            "gross_revenue": round(gross_rev, 2),
            "food_cost": round(food_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "total_tax_collected": round(tax_coll, 2),
            "net_revenue": round(net_rev, 2),
            "total_revenue": round(net_rev, 2),
            "paid_orders": paid_orders,
            "total_discounts": round(discounts, 2),
            "profit_margin_percent": profit_margin,
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

        # Month Chart
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

        # Today Chart
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

        if time_range == "today":
            active_chart = chart_today
        elif time_range in ("month", "this_month"):
            active_chart = chart_month
        elif time_range in ("7d", "last_7_days"):
            active_chart = chart_7d
        else:
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

        # 3. Daily Breakdown Rows (Grouped by Date & Branch)
        daily_query = (
            select(
                func.date(Bill.created_at).label("record_date"),
                Bill.branch_id,
                func.count(Bill.id).label("order_count"),
                func.coalesce(func.sum(Bill.subtotal), 0).label("subtotal"),
                func.coalesce(func.sum(Bill.discount_amount + Bill.offer_discount + Bill.wallet_discount), 0).label("discounts"),
                func.coalesce(func.sum(Bill.tax_total + Bill.service_charge_amount), 0).label("tax"),
                func.coalesce(func.sum(Bill.final_amount), 0).label("net_sales"),
            )
            .where(*conditions)
            .group_by(func.date(Bill.created_at), Bill.branch_id)
            .order_by(func.date(Bill.created_at).desc())
        )
        daily_res = await db.execute(daily_query)
        daily_rows = daily_res.all()

        branch_map = {b.id: b.name for b in branches}
        rows = []
        for idx, r in enumerate(daily_rows, start=1):
            n_sales = safe_float(r.net_sales)
            est_cost = round(safe_float(r.subtotal) * 0.30, 2)
            est_profit = round(n_sales - est_cost, 2)
            margin = round((est_profit / n_sales) * 100, 2) if n_sales > 0 else 0.0

            rows.append(
                {
                    "sr_no": idx,
                    "date": r.record_date.strftime("%d-%m-%Y") if r.record_date else "—",
                    "branch_id": r.branch_id,
                    "branch_name": branch_map.get(r.branch_id, f"Branch #{r.branch_id}"),
                    "paid_orders": safe_int(r.order_count),
                    "gross_subtotal": round(safe_float(r.subtotal), 2),
                    "discounts": round(safe_float(r.discounts), 2),
                    "taxes_collected": round(safe_float(r.tax), 2),
                    "estimated_food_cost": est_cost,
                    "net_sales": round(n_sales, 2),
                    "gross_profit": est_profit,
                    "profit_margin_percent": margin,
                }
            )

        return {
            "success": True,
            "report": "financial",
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
            "rows": rows,
            "pagination": {
                "page": 1,
                "page_size": len(rows) or 50,
                "total": len(rows),
                "total_pages": 1,
            },
        }

    @staticmethod
    def _empty_response(scope_meta, f_date, t_date, page, page_size):
        return {
            "success": True,
            "report": "financial",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "gross_revenue": 0.0,
                "food_cost": 0.0,
                "gross_profit": 0.0,
                "total_tax_collected": 0.0,
                "net_revenue": 0.0,
                "total_revenue": 0.0,
                "paid_orders": 0,
                "total_discounts": 0.0,
                "profit_margin_percent": 0.0,
            },
            "chart": [],
            "charts": {"7d": [], "month": [], "today": []},
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

        # Group by date & branch
        daily_res = await db.execute(
            select(
                func.date(Bill.created_at).label("rec_date"),
                Bill.branch_id,
                func.count(Bill.id).label("orders"),
                func.coalesce(func.sum(Bill.subtotal), 0).label("subtotal"),
                func.coalesce(func.sum(Bill.discount_amount + Bill.offer_discount + Bill.wallet_discount), 0).label("discounts"),
                func.coalesce(func.sum(Bill.tax_total), 0).label("tax_total"),
                func.coalesce(func.sum(Bill.service_charge_amount), 0).label("sc_amount"),
                func.coalesce(func.sum(Bill.final_amount), 0).label("final_sales"),
            )
            .where(*conditions)
            .group_by(func.date(Bill.created_at), Bill.branch_id)
            .order_by(func.date(Bill.created_at).desc())
        )
        daily_records = daily_res.all()

        tot_orders = sum(safe_int(r.orders) for r in daily_records)
        tot_subtotal = sum(safe_float(r.subtotal) for r in daily_records)
        tot_discounts = sum(safe_float(r.discounts) for r in daily_records)
        tot_taxes = sum(safe_float(r.tax_total + r.sc_amount) for r in daily_records)
        tot_sales = sum(safe_float(r.final_sales) for r in daily_records)
        est_tot_cost = round(tot_subtotal * 0.30, 2)
        tot_profit = round(tot_sales - est_tot_cost, 2)

        title = f"Financial Report - {scope_meta['branch_name']}" if not scope_meta['is_all_branches'] else f"Financial Report - {scope_meta['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope_meta["scope_name"],
            from_date=f_date,
            to_date=t_date,
        )

        # 1. Sheet 1: Financial Summary
        kpis = [
            ("GROSS REVENUE", f"₹{tot_subtotal:,.2f}", False),
            ("ESTIMATED FOOD COST", f"₹{est_tot_cost:,.2f}", False),
            ("TAXES COLLECTED", f"₹{tot_taxes:,.2f}", False),
            ("TOTAL NET REVENUE", f"₹{tot_sales:,.2f}", False),
            ("ESTIMATED GROSS PROFIT", f"₹{tot_profit:,.2f}", True),
        ]

        summary_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Date", ALIGN_CENTER, 14),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Paid Orders", ALIGN_RIGHT, 14),
            ("Gross Subtotal (₹)", ALIGN_RIGHT, 18),
            ("Discounts (₹)", ALIGN_RIGHT, 16),
            ("Taxes Collected (₹)", ALIGN_RIGHT, 18),
            ("Est. Cost (₹)", ALIGN_RIGHT, 16),
            ("Net Sales (₹)", ALIGN_RIGHT, 18),
            ("Gross Profit (₹)", ALIGN_RIGHT, 18),
            ("Profit Margin", ALIGN_RIGHT, 14),
        ]

        branch_map = {b.id: b.name for b in branches}
        summary_rows = []
        for idx, r in enumerate(daily_records, start=1):
            subt = safe_float(r.subtotal)
            disc = safe_float(r.discounts)
            tx = safe_float(r.tax_total + r.sc_amount)
            net_s = safe_float(r.final_sales)
            cost = round(subt * 0.30, 2)
            profit = round(net_s - cost, 2)
            margin = (profit / net_s) if net_s > 0 else 0.0

            summary_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (r.rec_date.strftime("%d-%m-%Y") if r.rec_date else "—", ALIGN_CENTER, None),
                    (r.branch_id, ALIGN_CENTER, None),
                    (branch_map.get(r.branch_id, f"Branch #{r.branch_id}"), ALIGN_LEFT, None),
                    (safe_int(r.orders), ALIGN_RIGHT, None),
                    (subt, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (disc, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (tx, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (cost, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (net_s, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (profit, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (f"{margin * 100:.2f}%", ALIGN_RIGHT, None),
                ]
            )

        summary_totals = {
            5: (tot_orders, None),
            6: (tot_subtotal, NUM_FMT_CURRENCY),
            7: (tot_discounts, NUM_FMT_CURRENCY),
            8: (tot_taxes, NUM_FMT_CURRENCY),
            9: (est_tot_cost, NUM_FMT_CURRENCY),
            10: (tot_sales, NUM_FMT_CURRENCY),
            11: (tot_profit, NUM_FMT_CURRENCY),
        }

        builder.add_summary_sheet(
            sheet_title="Financial Summary",
            kpis=kpis,
            headers=summary_headers,
            data_rows=summary_rows,
            totals_row=summary_totals,
            empty_message="No financial transactions recorded for the selected period.",
        )

        # 2. Sheet 2: Tax & Charge Breakdown
        tax_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Date", ALIGN_CENTER, 14),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Taxable Amount (₹)", ALIGN_RIGHT, 18),
            ("GST / Tax Total (₹)", ALIGN_RIGHT, 18),
            ("Service Charge (₹)", ALIGN_RIGHT, 18),
            ("Total Tax & Levies (₹)", ALIGN_RIGHT, 20),
        ]

        tax_rows = []
        tot_sc = sum(safe_float(r.sc_amount) for r in daily_records)
        tot_gst = sum(safe_float(r.tax_total) for r in daily_records)

        for idx, r in enumerate(daily_records, start=1):
            subt = safe_float(r.subtotal)
            tx = safe_float(r.tax_total)
            sc = safe_float(r.sc_amount)
            tax_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (r.rec_date.strftime("%d-%m-%Y") if r.rec_date else "—", ALIGN_CENTER, None),
                    (branch_map.get(r.branch_id, f"Branch #{r.branch_id}"), ALIGN_LEFT, None),
                    (subt, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (tx, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (sc, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (tx + sc, ALIGN_RIGHT, NUM_FMT_CURRENCY),
                ]
            )

        builder.add_details_sheet(
            sheet_title="Taxes Breakdown",
            details_header_title="🏛️  TAXES & CHARGES BREAKDOWN",
            headers=tax_headers,
            data_rows=tax_rows,
            totals_row={
                4: (tot_subtotal, NUM_FMT_CURRENCY),
                5: (tot_gst, NUM_FMT_CURRENCY),
                6: (tot_sc, NUM_FMT_CURRENCY),
                7: (tot_taxes, NUM_FMT_CURRENCY),
            },
            empty_message="No tax breakdown available.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Financial_Report_{branch_tag}_{f_date.strftime('%Y%m%d')}_{t_date.strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
