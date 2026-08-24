# app/reports/payment/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.payment.model import Payment
from app.accounts.bill.model import Bill
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


class PaymentReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        payment_method: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return PaymentReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        conditions = [
            Payment.branch_id.in_(branch_ids),
            Payment.payment_date >= start_dt,
            Payment.payment_date <= end_dt,
        ]

        if payment_method and payment_method != "all":
            conditions.append(Payment.payment_method.ilike(f"%{payment_method}%"))

        # Fetch all payments for breakdowns and summaries
        payments_query = (
            select(Payment)
            .where(*conditions)
            .order_by(Payment.payment_date.desc())
        )
        payments_res = await db.execute(payments_query)
        all_payments = payments_res.scalars().all()

        tot_payments = len(all_payments)
        tot_cash = 0.0
        tot_upi = 0.0
        tot_card = 0.0
        tot_other = 0.0
        tot_collected = 0.0

        for p in all_payments:
            p_amt = safe_float(p.paid_amount)
            tot_collected += p_amt

            method = (p.payment_method or "").lower()
            breakdown = p.payment_breakdown or []

            if breakdown and isinstance(breakdown, list):
                for b_item in breakdown:
                    m = (b_item.get("payment_method") or "").lower()
                    a = safe_float(b_item.get("payment_amount", 0))
                    if "cash" in m:
                        tot_cash += a
                    elif "upi" in m:
                        tot_upi += a
                    elif "card" in m:
                        tot_card += a
                    else:
                        tot_other += a
            else:
                if "cash" in method:
                    tot_cash += p_amt
                elif "upi" in method:
                    tot_upi += p_amt
                elif "card" in method:
                    tot_card += p_amt
                else:
                    tot_other += p_amt

        summary_data = {
            "total_payments": tot_payments,
            "cash_amount": round(tot_cash, 2),
            "upi_amount": round(tot_upi, 2),
            "card_amount": round(tot_card, 2),
            "total_collected": round(tot_collected, 2),
            "total_revenue": round(tot_collected, 2),
        }

        # 2. Charts (7d, Month, Today, Custom)
        today = date.today()
        seven_days_ago = today - timedelta(days=6)
        month_start = today.replace(day=1)

        # 7-Days Chart
        chart_7d = []
        for i in range(7):
            curr = seven_days_ago + timedelta(days=i)
            day_sum = sum(
                safe_float(p.paid_amount)
                for p in all_payments
                if p.payment_date and p.payment_date.date() == curr
            )
            day_count = sum(
                1 for p in all_payments if p.payment_date and p.payment_date.date() == curr
            )
            lbl = "Today" if curr == today else ("Yesterday" if curr == today - timedelta(days=1) else curr.strftime("%d-%m"))
            chart_7d.append({"date": str(curr), "label": lbl, "amount": round(day_sum, 2), "quantity": day_count})

        # Month Chart (Weekly Breakdown)
        weeks_def = [
            ("Week 1", 1, 7),
            ("Week 2", 8, 14),
            ("Week 3", 15, 21),
            ("Week 4", 22, 28),
            ("Week 5", 29, 31),
        ]
        chart_month = []
        for w_label, start_d, end_d in weeks_def:
            w_sum = sum(
                safe_float(p.paid_amount)
                for p in all_payments
                if p.payment_date and p.payment_date.month == today.month and start_d <= p.payment_date.day <= end_d
            )
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
        chart_today = []
        today_payments = [p for p in all_payments if p.payment_date and p.payment_date.date() == today]
        for slot_lbl, h_s, h_e in time_slots:
            slot_sum = sum(
                safe_float(p.paid_amount)
                for p in today_payments
                if h_s <= p.payment_date.hour < h_e
            )
            chart_today.append({"label": slot_lbl, "amount": round(slot_sum, 2), "quantity": 0.0})

        # Active chart selection
        if time_range == "today":
            active_chart = chart_today
        elif time_range in ("month", "this_month"):
            active_chart = chart_month
        elif time_range in ("7d", "last_7_days"):
            active_chart = chart_7d
        else:
            # Custom range by date
            date_map = {}
            for p in all_payments:
                if p.payment_date:
                    d_str = str(p.payment_date.date())
                    date_map[d_str] = date_map.get(d_str, 0.0) + safe_float(p.paid_amount)
            active_chart = [
                {"date": d_str, "label": d_str[5:], "amount": round(amt, 2), "quantity": 0.0}
                for d_str, amt in sorted(date_map.items())
            ]

        # 3. Top Payment Methods Ranking
        method_counts = {}
        method_amounts = {}
        for p in all_payments:
            m = (p.payment_method or "Cash").upper()
            method_counts[m] = method_counts.get(m, 0) + 1
            method_amounts[m] = method_amounts.get(m, 0.0) + safe_float(p.paid_amount)

        top_items = []
        sorted_methods = sorted(method_amounts.items(), key=lambda x: x[1], reverse=True)
        for idx, (m_name, m_amt) in enumerate(sorted_methods, start=1):
            pct = round((m_amt / tot_collected) * 100, 2) if tot_collected > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": idx,
                    "name": m_name,
                    "icon": "💳" if "CARD" in m_name else ("📱" if "UPI" in m_name else "💵"),
                    "quantity": float(method_counts.get(m_name, 0)),
                    "amount": round(m_amt, 2),
                    "percent": pct,
                }
            )

        # 4. Detailed Data Rows (Paginated)
        offset = max(page - 1, 0) * page_size
        paginated_payments = all_payments[offset : offset + page_size]

        # Join bill info for invoices
        bill_ids = [p.bill_id for p in paginated_payments if p.bill_id]
        bill_map = {}
        if bill_ids:
            b_res = await db.execute(select(Bill.id, Bill.invoice_no).where(Bill.id.in_(bill_ids)))
            bill_map = {row.id: row.invoice_no for row in b_res}

        rows = []
        for idx, p in enumerate(paginated_payments, start=offset + 1):
            inv_no = bill_map.get(p.bill_id, f"BILL-{p.bill_id}")
            p_date_str = p.payment_date.strftime("%d-%m-%Y %H:%M") if p.payment_date else "—"

            rows.append(
                {
                    "sr_no": idx,
                    "id": p.id,
                    "branch_id": p.branch_id,
                    "bill_id": p.bill_id,
                    "invoice_no": inv_no,
                    "payment_date": p_date_str,
                    "payment_method": (p.payment_method or "Cash").upper(),
                    "bill_amount": round(safe_float(p.bill_amount), 2),
                    "receive_amount": round(safe_float(p.receive_amount), 2),
                    "paid_amount": round(safe_float(p.paid_amount), 2),
                    "change_amount": round(safe_float(p.change_amount), 2),
                    "wallet_discount": round(safe_float(p.wallet_discount), 2),
                    "payment_reference": p.payment_reference or "—",
                    "notes": p.notes or "",
                }
            )

        total_pages = max((tot_payments + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "payment",
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
                "total": tot_payments,
                "total_pages": total_pages,
            },
        }

    @staticmethod
    def _empty_response(scope_meta, f_date, t_date, page, page_size):
        return {
            "success": True,
            "report": "payment",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_payments": 0,
                "cash_amount": 0.0,
                "upi_amount": 0.0,
                "card_amount": 0.0,
                "total_collected": 0.0,
                "total_revenue": 0.0,
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
    ) -> Tuple[io.BytesIO, str]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        conditions = [
            Payment.branch_id.in_(branch_ids),
            Payment.payment_date >= start_dt,
            Payment.payment_date <= end_dt,
        ]

        if payment_method and payment_method != "all":
            conditions.append(Payment.payment_method.ilike(f"%{payment_method}%"))

        payments_res = await db.execute(
            select(Payment).where(*conditions).order_by(Payment.payment_date.desc())
        )
        payments = payments_res.scalars().all()

        tot_payments = len(payments)
        tot_bill_amt = sum(safe_float(p.bill_amount) for p in payments)
        tot_paid = sum(safe_float(p.paid_amount) for p in payments)
        tot_change = sum(safe_float(p.change_amount) for p in payments)

        tot_cash = 0.0
        tot_upi = 0.0
        tot_card = 0.0

        for p in payments:
            p_amt = safe_float(p.paid_amount)
            method = (p.payment_method or "").lower()
            if "cash" in method:
                tot_cash += p_amt
            elif "upi" in method:
                tot_upi += p_amt
            elif "card" in method:
                tot_card += p_amt

        # Fetch bill invoice numbers
        bill_ids = [p.bill_id for p in payments if p.bill_id]
        bill_map = {}
        if bill_ids:
            b_res = await db.execute(select(Bill.id, Bill.invoice_no).where(Bill.id.in_(bill_ids)))
            bill_map = {row.id: row.invoice_no for row in b_res}

        title = f"Payment Report - {scope_meta['branch_name']}" if not scope_meta['is_all_branches'] else f"Payment Report - {scope_meta['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope_meta["scope_name"],
            from_date=f_date,
            to_date=t_date,
        )

        # 1. Sheet 1: Payment Summary
        kpis = [
            ("TOTAL PAYMENTS", str(tot_payments), False),
            ("CASH COLLECTED", f"₹{tot_cash:,.2f}", False),
            ("UPI COLLECTED", f"₹{tot_upi:,.2f}", False),
            ("CARD COLLECTED", f"₹{tot_card:,.2f}", False),
            ("TOTAL COLLECTED", f"₹{tot_paid:,.2f}", True),
        ]

        summary_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Payment ID", ALIGN_CENTER, 14),
            ("Invoice No", ALIGN_LEFT, 18),
            ("Payment Date", ALIGN_CENTER, 18),
            ("Payment Method", ALIGN_CENTER, 16),
            ("Bill Amount (₹)", ALIGN_RIGHT, 16),
            ("Received (₹)", ALIGN_RIGHT, 16),
            ("Paid / Settled (₹)", ALIGN_RIGHT, 18),
            ("Change (₹)", ALIGN_RIGHT, 14),
            ("Reference No", ALIGN_LEFT, 18),
            ("Notes", ALIGN_LEFT, 24),
        ]

        summary_rows = []
        for idx, p in enumerate(payments, start=1):
            inv_no = bill_map.get(p.bill_id, f"BILL-{p.bill_id}")
            p_dt = p.payment_date.strftime("%d-%m-%Y %H:%M") if p.payment_date else "—"

            summary_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (p.branch_id, ALIGN_CENTER, None),
                    (p.id, ALIGN_CENTER, None),
                    (inv_no, ALIGN_LEFT, None),
                    (p_dt, ALIGN_CENTER, None),
                    ((p.payment_method or "Cash").upper(), ALIGN_CENTER, None),
                    (safe_float(p.bill_amount), ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (safe_float(p.receive_amount), ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (safe_float(p.paid_amount), ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (safe_float(p.change_amount), ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (p.payment_reference or "—", ALIGN_LEFT, None),
                    (p.notes or "", ALIGN_LEFT, None),
                ]
            )

        summary_totals = {
            7: (tot_bill_amt, NUM_FMT_CURRENCY),
            9: (tot_paid, NUM_FMT_CURRENCY),
            10: (tot_change, NUM_FMT_CURRENCY),
        }

        builder.add_summary_sheet(
            sheet_title="Payment Summary",
            kpis=kpis,
            headers=summary_headers,
            data_rows=summary_rows,
            totals_row=summary_totals,
            empty_message="No payment transactions found for the selected period.",
        )

        # 2. Sheet 2: Payment Method Breakdown
        method_headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Payment Method", ALIGN_LEFT, 22),
            ("Transactions Count", ALIGN_RIGHT, 18),
            ("Total Amount (₹)", ALIGN_RIGHT, 20),
            ("Share of Total %", ALIGN_RIGHT, 18),
        ]

        method_groups = {}
        for p in payments:
            m = (p.payment_method or "Cash").upper()
            method_groups.setdefault(m, {"count": 0, "amount": 0.0})
            method_groups[m]["count"] += 1
            method_groups[m]["amount"] += safe_float(p.paid_amount)

        method_rows = []
        for idx, (m_name, m_data) in enumerate(method_groups.items(), start=1):
            pct = (m_data["amount"] / tot_paid) if tot_paid > 0 else 0.0
            method_rows.append(
                [
                    (idx, ALIGN_CENTER, None),
                    (m_name, ALIGN_LEFT, None),
                    (m_data["count"], ALIGN_RIGHT, None),
                    (m_data["amount"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (f"{pct * 100:.2f}%", ALIGN_RIGHT, None),
                ]
            )

        builder.add_details_sheet(
            sheet_title="Method Split",
            details_header_title="💳  PAYMENT METHODS DISTRIBUTION",
            headers=method_headers,
            data_rows=method_rows,
            totals_row={3: (tot_payments, None), 4: (tot_paid, NUM_FMT_CURRENCY)},
            empty_message="No payment method splits available.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Payment_Report_{branch_tag}_{f_date.strftime('%Y%m%d')}_{t_date.strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
