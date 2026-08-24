# app/reports/customer/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func, case
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.customer.model import Customer
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


class CustomerReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        customer_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return CustomerReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        # Customer conditions
        cust_conditions = [Customer.branch_id.in_(branch_ids)]
        if customer_type and customer_type != "all":
            cust_conditions.append(Customer.customer_type.ilike(f"%{customer_type}%"))

        # 1. Summary Aggregations
        tot_cust_res = await db.execute(
            select(
                func.count(Customer.id).label("total_customers"),
                func.coalesce(
                    func.sum(
                        case(
                            ((Customer.created_at >= start_dt) & (Customer.created_at <= end_dt), 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("new_customers"),
                func.coalesce(
                    func.sum(
                        case((Customer.total_orders > 1, 1), else_=0)
                    ),
                    0,
                ).label("returning_customers"),
                func.coalesce(func.sum(Customer.total_spend), 0).label("total_spend"),
                func.coalesce(func.sum(Customer.wallet_balance), 0).label("total_wallet"),
            ).where(*cust_conditions)
        )
        c_row = tot_cust_res.one()

        tot_cust = safe_int(c_row.total_customers)
        new_cust = safe_int(c_row.new_customers)
        ret_cust = safe_int(c_row.returning_customers)
        tot_spend = safe_float(c_row.total_spend)
        tot_wallet = safe_float(c_row.total_wallet)
        avg_spend = round(tot_spend / tot_cust, 2) if tot_cust > 0 else 0.0

        summary_data = {
            "total_customers": tot_cust,
            "new_customers": new_cust,
            "returning_customers": ret_cust,
            "total_spend": round(tot_spend, 2),
            "average_spend": avg_spend,
            "total_wallet_balance": round(tot_wallet, 2),
        }

        # 2. Charts: Customer registrations by day
        today = date.today()
        seven_days_ago = today - timedelta(days=6)
        month_start = today.replace(day=1)

        c_7d_query = (
            select(
                func.date(Customer.created_at).label("reg_date"),
                func.count(Customer.id).label("count"),
            )
            .where(
                Customer.branch_id.in_(branch_ids),
                Customer.created_at >= datetime.combine(seven_days_ago, datetime.min.time()),
                Customer.created_at <= datetime.combine(today, datetime.max.time()),
            )
            .group_by(func.date(Customer.created_at))
        )
        c_7d_res = await db.execute(c_7d_query)
        c_7d_map = {str(row.reg_date): safe_int(row.count) for row in c_7d_res}

        chart_7d = []
        for i in range(7):
            curr = seven_days_ago + timedelta(days=i)
            curr_str = str(curr)
            cnt = c_7d_map.get(curr_str, 0)
            lbl = "Today" if curr == today else ("Yesterday" if curr == today - timedelta(days=1) else curr.strftime("%d-%m"))
            chart_7d.append({"date": curr_str, "label": lbl, "amount": float(cnt), "quantity": float(cnt)})

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
                func.extract("day", Customer.created_at).label("day"),
                func.count(Customer.id).label("count"),
            )
            .where(
                Customer.branch_id.in_(branch_ids),
                Customer.created_at >= datetime.combine(month_start, datetime.min.time()),
                Customer.created_at <= datetime.combine(today, datetime.max.time()),
            )
            .group_by(func.extract("day", Customer.created_at))
        )
        c_m_res = await db.execute(c_m_query)
        day_map = {int(row.day): safe_int(row.count) for row in c_m_res}

        chart_month = []
        for w_label, start_d, end_d in weeks_def:
            w_sum = sum(day_map.get(d, 0) for d in range(start_d, end_d + 1))
            chart_month.append({"label": w_label, "amount": float(w_sum), "quantity": float(w_sum)})

        # Active Chart
        if time_range in ("month", "this_month"):
            active_chart = chart_month
        else:
            active_chart = chart_7d

        # 3. Top Spending Customers
        top_cust_query = (
            select(Customer)
            .where(*cust_conditions)
            .order_by(Customer.total_spend.desc())
            .limit(10)
        )
        top_cust_res = await db.execute(top_cust_query)
        top_cust_rows = top_cust_res.scalars().all()

        top_items = []
        for idx, c in enumerate(top_cust_rows, start=1):
            sp = safe_float(c.total_spend)
            pct = round((sp / tot_spend) * 100, 2) if tot_spend > 0 else 0.0
            top_items.append(
                {
                    "rank": idx,
                    "id": c.id,
                    "name": c.name,
                    "icon": "👑" if c.is_vip else "👤",
                    "quantity": float(c.total_orders or 0),
                    "amount": round(sp, 2),
                    "percent": pct,
                }
            )

        # 4. Paginated Customer Directory
        total_records_res = await db.execute(select(func.count(Customer.id)).where(*cust_conditions))
        total_records = total_records_res.scalar() or 0

        offset = max(page - 1, 0) * page_size
        customers_query = (
            select(Customer)
            .where(*cust_conditions)
            .order_by(Customer.total_spend.desc(), Customer.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        customers_res = await db.execute(customers_query)
        customers = customers_res.scalars().all()

        branch_map = {b.id: b.name for b in branches}
        rows = []
        for idx, c in enumerate(customers, start=offset + 1):
            f_visit = c.first_visit_at.strftime("%d-%m-%Y") if c.first_visit_at else "—"
            l_visit = c.last_visit_at.strftime("%d-%m-%Y") if c.last_visit_at else "—"
            rows.append(
                {
                    "sr_no": idx,
                    "id": c.id,
                    "branch_id": c.branch_id,
                    "branch_name": branch_map.get(c.branch_id, f"Branch #{c.branch_id}"),
                    "name": c.name,
                    "phone": c.phone or "—",
                    "email": c.email or "—",
                    "customer_type": c.customer_type or "Regular",
                    "current_rank": c.current_rank or "Bronze",
                    "is_vip": "VIP" if c.is_vip else "Standard",
                    "total_visits": safe_int(c.total_visits),
                    "total_orders": safe_int(c.total_orders),
                    "total_spend": round(safe_float(c.total_spend), 2),
                    "average_order_value": round(safe_float(c.average_order_value), 2),
                    "wallet_balance": round(safe_float(c.wallet_balance), 2),
                    "first_visit": f_visit,
                    "last_visit": l_visit,
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "customer",
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
                "today": chart_7d,
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
            "report": "customer",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_customers": 0,
                "new_customers": 0,
                "returning_customers": 0,
                "total_spend": 0.0,
                "average_spend": 0.0,
                "total_wallet_balance": 0.0,
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
        customer_type: Optional[str] = None,
    ) -> Tuple[io.BytesIO, str]:
        data = await CustomerReportService.get_report_data(
            db=db,
            client_id=client_id,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            customer_type=customer_type,
            page=1,
            page_size=10000,
        )
        scope = data["scope"]
        summary = data["summary"]
        rows = data["rows"]

        title = f"Customer Report - {scope['branch_name']}" if not scope['is_all_branches'] else f"Customer Report - {scope['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope["scope_name"],
            from_date=scope["date_from"],
            to_date=scope["date_to"],
        )

        kpis = [
            ("TOTAL CUSTOMERS", str(summary["total_customers"]), False),
            ("NEW CUSTOMERS", str(summary["new_customers"]), False),
            ("RETURNING CUSTOMERS", str(summary["returning_customers"]), False),
            ("AVERAGE SPEND", f"₹{summary['average_spend']:,.2f}", False),
            ("TOTAL SPEND", f"₹{summary['total_spend']:,.2f}", True),
        ]

        headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Customer Name", ALIGN_LEFT, 24),
            ("Phone", ALIGN_CENTER, 16),
            ("Email", ALIGN_LEFT, 22),
            ("Type", ALIGN_CENTER, 14),
            ("Rank", ALIGN_CENTER, 12),
            ("VIP", ALIGN_CENTER, 10),
            ("Visits", ALIGN_RIGHT, 10),
            ("Orders", ALIGN_RIGHT, 10),
            ("Avg Order (₹)", ALIGN_RIGHT, 16),
            ("Total Spend (₹)", ALIGN_RIGHT, 18),
            ("Wallet Balance (₹)", ALIGN_RIGHT, 18),
        ]

        summary_rows = []
        tot_spend = sum(r["total_spend"] for r in rows)
        tot_wallet = sum(r["wallet_balance"] for r in rows)

        for r in rows:
            summary_rows.append(
                [
                    (r["sr_no"], ALIGN_CENTER, None),
                    (r["branch_id"], ALIGN_CENTER, None),
                    (r["branch_name"], ALIGN_LEFT, None),
                    (r["name"], ALIGN_LEFT, None),
                    (r["phone"], ALIGN_CENTER, None),
                    (r["email"], ALIGN_LEFT, None),
                    (r["customer_type"], ALIGN_CENTER, None),
                    (r["current_rank"], ALIGN_CENTER, None),
                    (r["is_vip"], ALIGN_CENTER, None),
                    (r["total_visits"], ALIGN_RIGHT, None),
                    (r["total_orders"], ALIGN_RIGHT, None),
                    (r["average_order_value"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (r["total_spend"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (r["wallet_balance"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                ]
            )

        builder.add_summary_sheet(
            sheet_title="Customer Summary",
            kpis=kpis,
            headers=headers,
            data_rows=summary_rows,
            totals_row={13: (tot_spend, NUM_FMT_CURRENCY), 14: (tot_wallet, NUM_FMT_CURRENCY)},
            empty_message="No customer profiles recorded.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Customer_Report_{branch_tag}_{scope['date_from'].strftime('%Y%m%d')}_{scope['date_to'].strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
