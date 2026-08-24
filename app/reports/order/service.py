# app/reports/order/service.py

import io
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select, func, case
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.order.model import Order, OrderItem
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


class OrderReportService:

    @staticmethod
    async def get_report_data(
        db: AsyncSession,
        client_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        time_range: Optional[str] = None,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        client, branches, scope_meta = await validate_and_get_scope(
            db=db, client_id=client_id, branch_id=branch_id
        )
        f_date, t_date = resolve_date_range(from_date, to_date, time_range)
        branch_ids = scope_meta["branch_ids"]

        if not branch_ids:
            return OrderReportService._empty_response(scope_meta, f_date, t_date, page, page_size)

        start_dt = datetime.combine(f_date, datetime.min.time())
        end_dt = datetime.combine(t_date, datetime.max.time())

        conditions = [
            Order.branch_id.in_(branch_ids),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ]

        if order_type and order_type != "all":
            conditions.append(Order.order_type == order_type)
        if status and status != "all":
            conditions.append(Order.status == status)

        # 1. Summary Aggregations
        orders_summary = await db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(
                    func.sum(
                        case((Order.order_type == "dine_in", 1), else_=0)
                    ),
                    0,
                ).label("dine_in_orders"),
                func.coalesce(
                    func.sum(
                        case((Order.order_type == "takeaway", 1), else_=0)
                    ),
                    0,
                ).label("takeaway_orders"),
                func.coalesce(
                    func.sum(
                        case((Order.order_type == "delivery", 1), else_=0)
                    ),
                    0,
                ).label("delivery_orders"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_amount"),
            ).where(*conditions)
        )
        s_row = orders_summary.one()

        summary_data = {
            "total_orders": safe_int(s_row.total_orders),
            "total_bills": safe_int(s_row.total_orders),
            "dine_in_orders": safe_int(s_row.dine_in_orders),
            "takeaway_orders": safe_int(s_row.takeaway_orders),
            "delivery_orders": safe_int(s_row.delivery_orders),
            "total_amount": round(safe_float(s_row.total_amount), 2),
            "total_sales": round(safe_float(s_row.total_amount), 2),
        }

        # 2. Charts: Orders per day
        today = date.today()
        seven_days_ago = today - timedelta(days=6)
        month_start = today.replace(day=1)

        c_7d_query = (
            select(
                func.date(Order.created_at).label("o_date"),
                func.count(Order.id).label("count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("amount"),
            )
            .where(
                Order.branch_id.in_(branch_ids),
                Order.created_at >= datetime.combine(seven_days_ago, datetime.min.time()),
                Order.created_at <= datetime.combine(today, datetime.max.time()),
            )
            .group_by(func.date(Order.created_at))
        )
        c_7d_res = await db.execute(c_7d_query)
        c_7d_map = {str(row.o_date): (safe_int(row.count), safe_float(row.amount)) for row in c_7d_res}

        chart_7d = []
        for i in range(7):
            curr = seven_days_ago + timedelta(days=i)
            curr_str = str(curr)
            cnt, amt = c_7d_map.get(curr_str, (0, 0.0))
            lbl = "Today" if curr == today else ("Yesterday" if curr == today - timedelta(days=1) else curr.strftime("%d-%m"))
            chart_7d.append({"date": curr_str, "label": lbl, "amount": round(amt, 2), "quantity": float(cnt)})

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
                func.extract("day", Order.created_at).label("day"),
                func.count(Order.id).label("count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("amount"),
            )
            .where(
                Order.branch_id.in_(branch_ids),
                Order.created_at >= datetime.combine(month_start, datetime.min.time()),
                Order.created_at <= datetime.combine(today, datetime.max.time()),
            )
            .group_by(func.extract("day", Order.created_at))
        )
        c_m_res = await db.execute(c_m_query)
        day_map = {int(row.day): (safe_int(row.count), safe_float(row.amount)) for row in c_m_res}

        chart_month = []
        for w_label, start_d, end_d in weeks_def:
            w_cnt = sum(day_map.get(d, (0, 0.0))[0] for d in range(start_d, end_d + 1))
            w_amt = sum(day_map.get(d, (0, 0.0))[1] for d in range(start_d, end_d + 1))
            chart_month.append({"label": w_label, "amount": round(w_amt, 2), "quantity": float(w_cnt)})

        active_chart = chart_month if time_range in ("month", "this_month") else chart_7d

        # 3. Paginated Orders
        total_records = summary_data["total_orders"]
        offset = max(page - 1, 0) * page_size

        orders_res = await db.execute(
            select(Order)
            .options(
                joinedload(Order.branch),
                joinedload(Order.customer),
                joinedload(Order.table),
            )
            .where(*conditions)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        orders = orders_res.scalars().all()

        rows = []
        for idx, o in enumerate(orders, start=offset + 1):
            b_name = o.branch.name if o.branch else f"Branch #{o.branch_id}"
            cust_name = o.customer_name or (o.customer.name if o.customer else "Walk-in")
            o_type = o.order_type.value if hasattr(o.order_type, "value") else str(o.order_type or "dine_in")

            rows.append(
                {
                    "sr_no": idx,
                    "id": o.id,
                    "branch_id": o.branch_id,
                    "branch_name": b_name,
                    "order_type": o_type.replace("_", " ").title(),
                    "table_name": o.table.name if o.table else "—",
                    "customer_name": cust_name,
                    "customer_phone": o.customer_phone or "—",
                    "status": (o.status or "pending").title(),
                    "total_amount": round(safe_float(o.total_amount), 2),
                    "created_at": o.created_at.strftime("%d-%m-%Y %H:%M") if o.created_at else "—",
                    "notes": o.notes or "",
                }
            )

        total_pages = max((total_records + page_size - 1) // page_size, 1)

        return {
            "success": True,
            "report": "order",
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
            "report": "order",
            "scope": {**scope_meta, "date_from": f_date, "date_to": t_date},
            "summary": {
                "total_orders": 0,
                "total_bills": 0,
                "dine_in_orders": 0,
                "takeaway_orders": 0,
                "delivery_orders": 0,
                "total_amount": 0.0,
                "total_sales": 0.0,
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
        order_type: Optional[str] = None,
    ) -> Tuple[io.BytesIO, str]:
        data = await OrderReportService.get_report_data(
            db=db,
            client_id=client_id,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            order_type=order_type,
            page=1,
            page_size=10000,
        )
        scope = data["scope"]
        summary = data["summary"]
        rows = data["rows"]

        title = f"Orders Report - {scope['branch_name']}" if not scope['is_all_branches'] else f"Orders Report - {scope['client_name'] or 'All Branches'}"

        builder = ExcelReportBuilder(
            report_title=title,
            scope_name=scope["scope_name"],
            from_date=scope["date_from"],
            to_date=scope["date_to"],
        )

        kpis = [
            ("TOTAL ORDERS", str(summary["total_orders"]), False),
            ("DINE-IN ORDERS", str(summary["dine_in_orders"]), False),
            ("TAKEAWAY ORDERS", str(summary["takeaway_orders"]), False),
            ("DELIVERY ORDERS", str(summary["delivery_orders"]), False),
            ("TOTAL BILLED AMOUNT", f"₹{summary['total_amount']:,.2f}", True),
        ]

        headers = [
            ("Sr. No.", ALIGN_CENTER, 8),
            ("Branch ID", ALIGN_CENTER, 12),
            ("Branch Name", ALIGN_LEFT, 22),
            ("Order ID", ALIGN_CENTER, 12),
            ("Date & Time", ALIGN_CENTER, 18),
            ("Order Type", ALIGN_CENTER, 14),
            ("Table", ALIGN_CENTER, 12),
            ("Customer Name", ALIGN_LEFT, 22),
            ("Customer Phone", ALIGN_CENTER, 16),
            ("Status", ALIGN_CENTER, 14),
            ("Order Total (₹)", ALIGN_RIGHT, 18),
            ("Notes", ALIGN_LEFT, 24),
        ]

        summary_rows = []
        tot_amt = sum(r["total_amount"] for r in rows)

        for r in rows:
            summary_rows.append(
                [
                    (r["sr_no"], ALIGN_CENTER, None),
                    (r["branch_id"], ALIGN_CENTER, None),
                    (r["branch_name"], ALIGN_LEFT, None),
                    (r["id"], ALIGN_CENTER, None),
                    (r["created_at"], ALIGN_CENTER, None),
                    (r["order_type"], ALIGN_CENTER, None),
                    (r["table_name"], ALIGN_CENTER, None),
                    (r["customer_name"], ALIGN_LEFT, None),
                    (r["customer_phone"], ALIGN_CENTER, None),
                    (r["status"], ALIGN_CENTER, None),
                    (r["total_amount"], ALIGN_RIGHT, NUM_FMT_CURRENCY),
                    (r["notes"], ALIGN_LEFT, None),
                ]
            )

        builder.add_summary_sheet(
            sheet_title="Orders Summary",
            kpis=kpis,
            headers=headers,
            data_rows=summary_rows,
            totals_row={11: (tot_amt, NUM_FMT_CURRENCY)},
            empty_message="No orders recorded for the selected period.",
        )

        excel_buf = builder.build()
        branch_tag = f"Branch_{branch_id}" if branch_id else f"Client_{client_id or 'All'}"
        filename = f"Order_Report_{branch_tag}_{scope['date_from'].strftime('%Y%m%d')}_{scope['date_to'].strftime('%Y%m%d')}.xlsx"
        return excel_buf, filename
