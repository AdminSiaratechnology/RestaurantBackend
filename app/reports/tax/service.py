# app/reports/tax/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
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


class TaxReportService:

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
            return TaxReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

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
            func.count(Bill.id).label("total_invoices"),
            func.coalesce(func.sum(Bill.subtotal), 0).label("taxable_amount"),
            func.coalesce(func.sum(Bill.cgst_amount), 0).label("cgst_amount"),
            func.coalesce(func.sum(Bill.sgst_amount), 0).label("sgst_amount"),
            func.coalesce(func.sum(getattr(Bill, "vat_amount", 0)), 0).label("vat_amount"),
            func.coalesce(func.sum(Bill.service_charge_amount), 0).label("service_charge_amount"),
            func.coalesce(func.sum(Bill.tax_total + Bill.service_charge_amount), 0).label("total_tax_collected"),
        ).where(*conditions)

        summary_res = await db.execute(summary_query)
        s_row = summary_res.one()

        summary_data = {
            "total_invoices": safe_int(s_row.total_invoices),
            "taxable_amount": round(safe_float(s_row.taxable_amount), 2),
            "cgst_amount": round(safe_float(s_row.cgst_amount), 2),
            "sgst_amount": round(safe_float(s_row.sgst_amount), 2),
            "vat_amount": round(safe_float(getattr(s_row, "vat_amount", 0)), 2),
            "service_charge_amount": round(safe_float(s_row.service_charge_amount), 2),
            "total_tax_collected": round(safe_float(s_row.total_tax_collected), 2),
            "total_tax": round(safe_float(s_row.total_tax_collected), 2),
        }

        # 2. Charts: Taxes collected per day
        today = date.today()
        seven_days_ago = today - timedelta(days=6)
        month_start = today.replace(day=1)

        c_7d_query = (
            select(
                func.date(Bill.created_at).label("bill_date"),
                func.coalesce(func.sum(Bill.tax_total + Bill.service_charge_amount), 0).label("amount"),
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

        active_chart = chart_7d

        # 3. Paginated Detailed Tax Invoices
        total_records_res = await db.execute(select(func.count(Bill.id)).where(*conditions))
        total_records = total_records_res.scalar() or 0

        offset = max(page - 1, 0) * page_size
        bills_res = await db.execute(
            select(Bill)
            .options(joinedload(Bill.branch))
            .where(*conditions)
            .order_by(Bill.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        bills = bills_res.scalars().all()

        rows = []
        for idx, b in enumerate(bills, start=offset + 1):
            b_name = b.branch.name if b.branch else f"Branch #{b.branch_id}"
            inv_date = b.created_at.strftime("%d-%m-%Y %H:%M") if b.created_at else "—"
            b_tax_type = str(getattr(b, "tax_type", None) or (b.branch.tax_type if b.branch else "GST") or "GST").upper()

            rows.append(
                {
                    "sr_no": idx,
                    "id": b.id,
                    "branch_id": b.branch_id,
                    "branch_name": b_name,
                    "invoice_no": b.invoice_no,
                    "invoice_date": inv_date,
                    "subtotal": round(safe_float(b.subtotal), 2),
                    "tax_type": b_tax_type,
                    "cgst_percent": round(safe_float(b.cgst_percent), 2),
                    "cgst_amount": round(safe_float(b.cgst_amount), 2),
                    "sgst_percent": round(safe_float(b.sgst_percent), 2),
                    "sgst_amount": round(safe_float(b.sgst_amount), 2),
                    "vat_percent": round(safe_float(getattr(b, "vat_percent", 0)), 2),
                    "vat_amount": round(safe_float(getattr(b, "vat_amount", 0)), 2),
                    "service_charge_percent": round(safe_float(b.service_charge_percent), 2),
                    "service_charge_amount": round(safe_float(b.service_charge_amount), 2),
                    "total_tax_collected": round(safe_float(b.tax_total + b.service_charge_amount), 2),
                    "final_amount": round(safe_float(b.final_amount), 2),
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "tax",
            "scope": {
                **scope_meta,
                "date_from": f_date,
                "date_to": t_date,
            },
            "summary": summary_data,
            "chart": active_chart,
            "charts": {
                "7d": chart_7d,
                "month": chart_7d,
                "today": chart_7d,
            },
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
            "report": "tax",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_invoices": 0,
                "taxable_amount": 0.0,
                "cgst_amount": 0.0,
                "sgst_amount": 0.0,
                "service_charge_amount": 0.0,
                "total_tax_collected": 0.0,
                "total_tax": 0.0,
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
        data = await TaxReportService.get_report_data(
            db=db,
            client_id=client_id,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            page=1,
            page_size=10000,
        )
        scope = data["scope"]
        summary = data["summary"]
        rows = data["rows"]

        title = f"Tax Report - {scope['branch_name']}" if not scope['is_all_branches'] else f"Tax Report - {scope['client_name'] or 'All Branches'}"

        curr_code, curr_symbol, dec_places = await get_branch_currency_settings_from_db(branch_id, db)
        num_fmt_curr = get_excel_currency_num_format(currency_symbol=curr_symbol, decimal_places=dec_places)

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope["scope_name"],
            from_date=scope["date_from"],
            to_date=scope["date_to"],
        )

        kpis = [
            ("TOTAL INVOICES", str(summary["total_invoices"]), False),
            ("TAXABLE AMOUNT", format_currency(summary['taxable_amount'], currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("CGST COLLECTED", format_currency(summary['cgst_amount'], currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("SGST COLLECTED", format_currency(summary['sgst_amount'], currency_symbol=curr_symbol, decimal_places=dec_places), False),
            ("TOTAL TAX COLLECTED", format_currency(summary['total_tax_collected'], currency_symbol=curr_symbol, decimal_places=dec_places), True),
        ]

        headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Invoice No", ALIGN_LEFT, 18),
            ("Invoice Date", ALIGN_CENTER, 18),
            (f"Taxable Subtotal ({curr_symbol})", ALIGN_RIGHT, 18),
            ("CGST %", ALIGN_RIGHT, 10),
            (f"CGST ({curr_symbol})", ALIGN_RIGHT, 14),
            ("SGST %", ALIGN_RIGHT, 10),
            (f"SGST ({curr_symbol})", ALIGN_RIGHT, 14),
            (f"Service Charge ({curr_symbol})", ALIGN_RIGHT, 18),
            (f"Total Tax Collected ({curr_symbol})", ALIGN_RIGHT, 20),
            (f"Final Bill ({curr_symbol})", ALIGN_RIGHT, 18),
        ]

        summary_rows = []
        tot_sub = sum(r["subtotal"] for r in rows)
        tot_cgst = sum(r["cgst_amount"] for r in rows)
        tot_sgst = sum(r["sgst_amount"] for r in rows)
        tot_sc = sum(r["service_charge_amount"] for r in rows)
        tot_tax_all = sum(r["total_tax_collected"] for r in rows)
        tot_final = sum(r["final_amount"] for r in rows)

        for r in rows:
            summary_rows.append(
                [
                    (r["sr_no"], ALIGN_CENTER, None),
                    (r["branch_id"], ALIGN_CENTER, None),
                    (r["branch_name"], ALIGN_LEFT, None),
                    (r["invoice_no"], ALIGN_LEFT, None),
                    (r["invoice_date"], ALIGN_CENTER, None),
                    (r["subtotal"], ALIGN_RIGHT, num_fmt_curr),
                    (f"{r['cgst_percent']:.2f}%", ALIGN_RIGHT, None),
                    (r["cgst_amount"], ALIGN_RIGHT, num_fmt_curr),
                    (f"{r['sgst_percent']:.2f}%", ALIGN_RIGHT, None),
                    (r["sgst_amount"], ALIGN_RIGHT, num_fmt_curr),
                    (r["service_charge_amount"], ALIGN_RIGHT, num_fmt_curr),
                    (r["total_tax_collected"], ALIGN_RIGHT, num_fmt_curr),
                    (r["final_amount"], ALIGN_RIGHT, num_fmt_curr),
                ]
            )

        builder.add_summary_sheet(
            sheet_title="Tax Summary",
            kpis=kpis,
            headers=headers,
            data_rows=summary_rows,
            totals_row={
                6: (tot_sub, num_fmt_curr),
                8: (tot_cgst, num_fmt_curr),
                10: (tot_sgst, num_fmt_curr),
                11: (tot_sc, num_fmt_curr),
                12: (tot_tax_all, num_fmt_curr),
                13: (tot_final, num_fmt_curr),
            },
            empty_message="No taxable transactions recorded for the selected period.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Tax_Report_{branch_tag}_{scope['date_from'].strftime('%Y%m%d')}_{scope['date_to'].strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
