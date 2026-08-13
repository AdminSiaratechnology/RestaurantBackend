# app/accounts/reports/service/payment_report.py

from sqlalchemy import select, func
from datetime import datetime, date, timedelta

from app.accounts.payment.model import Payment
from app.core.cache import Cache


async def payment_report_service(
    db,
    branch_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    cache_key = f"report:{branch_id or 'all'}:payment_report:{from_date or 'all'}_{to_date or 'all'}"
    cached = await Cache.get(cache_key)
    if cached:
        return cached
    query = select(Payment)

    if branch_id:
        query = query.where(
            Payment.branch_id == branch_id
        )

    if from_date:
        query = query.where(
            Payment.payment_date >= datetime.combine(
                from_date,
                datetime.min.time()
            )
        )

    if to_date:
        query = query.where(
            Payment.payment_date <= datetime.combine(
                to_date,
                datetime.max.time()
            )
        )

    result = await db.execute(query)

    payments = result.scalars().all()

    cash_orders = 0
    upi_orders = 0
    card_orders = 0

    revenue_cash = 0
    revenue_upi = 0
    revenue_card = 0
    revenue_credit = 0

    for payment in payments:

        breakdown = payment.payment_breakdown or []

        for item in breakdown:

            method = item.get("payment_method")
            amount = item.get("payment_amount", 0)

            if method == "cash":
                cash_orders += 1
                revenue_cash += amount

            elif method == "upi":
                upi_orders += 1
                revenue_upi += amount

            elif method == "card":
                card_orders += 1
                revenue_card += amount

            elif method == "credit":
                revenue_credit += amount

    total_revenue = (
        revenue_cash +
        revenue_upi +
        revenue_card +
        revenue_credit
    )

    result = {
        "cards": {
            "cash_orders": cash_orders,
            "upi_orders": upi_orders,
            "card_orders": card_orders,
            "total_revenue": round(total_revenue, 2)
        },

        "payment_method_split": [
            {
                "method": "Cash",
                "count": cash_orders
            },
            {
                "method": "UPI",
                "count": upi_orders
            },
            {
                "method": "Card",
                "count": card_orders
            }
        ],

        "revenue_by_payment_method": [
            {
                "method": "Cash",
                "amount": round(revenue_cash, 2)
            },
            {
                "method": "UPI",
                "amount": round(revenue_upi, 2)
            },
            {
                "method": "Card",
                "amount": round(revenue_card, 2)
            },
            {
                "method": "Credit",
                "amount": round(revenue_credit, 2)
            }
        ]
    }
    await Cache.set(cache_key, result, expire=21600)
    return result


# app/accounts/reports/service/payment_report_all_branches.py

from collections import defaultdict
from datetime import datetime, date
from sqlalchemy import select

from app.accounts.payment.model import Payment
from app.accounts.branch.model import Branch


async def payment_report_all_branches_service(
    db,
    client_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
):
    cache_key = f"report:all:payment_report_all:{client_id}:{from_date or 'all'}_{to_date or 'all'}"
    cached = await Cache.get(cache_key)
    if cached:
        return cached
    query = (
        select(Payment, Branch)
        .join(
            Branch,
            Payment.branch_id == Branch.id
        )
        .where(
            Branch.client_id == client_id
        )
    )

    if from_date:
        query = query.where(
            Payment.payment_date >= datetime.combine(
                from_date,
                datetime.min.time()
            )
        )

    if to_date:
        query = query.where(
            Payment.payment_date <= datetime.combine(
                to_date,
                datetime.max.time()
            )
        )

    result = await db.execute(query)
    rows = result.all()

    branch_data = defaultdict(
        lambda: {
            "branch_id": None,
            "branch_name": "",
            "cash_orders": 0,
            "upi_orders": 0,
            "card_orders": 0,
            "credit_orders": 0,
            "revenue_cash": 0,
            "revenue_upi": 0,
            "revenue_card": 0,
            "revenue_credit": 0,
            "total_revenue": 0,
        }
    )

    total_cash_orders = 0
    total_upi_orders = 0
    total_card_orders = 0
    total_credit_orders = 0

    total_revenue = 0

    for payment, branch in rows:

        data = branch_data[branch.id]

        data["branch_id"] = branch.id
        data["branch_name"] = branch.name

        breakdown = payment.payment_breakdown or []

        for item in breakdown:

            method = item.get("payment_method")
            amount = float(item.get("payment_amount", 0))

            if method == "cash":
                data["cash_orders"] += 1
                data["revenue_cash"] += amount
                total_cash_orders += 1

            elif method == "upi":
                data["upi_orders"] += 1
                data["revenue_upi"] += amount
                total_upi_orders += 1

            elif method == "card":
                data["card_orders"] += 1
                data["revenue_card"] += amount
                total_card_orders += 1

            elif method == "credit":
                data["credit_orders"] += 1
                data["revenue_credit"] += amount
                total_credit_orders += 1

    branches = []

    for branch in branch_data.values():

        branch["total_revenue"] = round(
            branch["revenue_cash"]
            + branch["revenue_upi"]
            + branch["revenue_card"]
            + branch["revenue_credit"],
            2
        )

        total_revenue += branch["total_revenue"]

        branches.append(branch)

    return {
        "summary": {
            "total_branches": len(branches),
            "cash_orders": total_cash_orders,
            "upi_orders": total_upi_orders,
            "card_orders": total_card_orders,
            "credit_orders": total_credit_orders,
            "total_revenue": round(total_revenue, 2)
        },
        "branches": branches
    }
    await Cache.set(cache_key, result, expire=21600)
    return result


from datetime import datetime, date
from sqlalchemy import select

from app.accounts.payment.model import Payment


async def payment_method_totals_service(
    db,
    branch_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    cache_key = f"report:{branch_id or 'all'}:payment_totals:{from_date or 'all'}_{to_date or 'all'}"
    cached = await Cache.get(cache_key)
    if cached:
        return cached
    query = select(Payment)

    if branch_id:
        query = query.where(
            Payment.branch_id == branch_id
        )

    if from_date:
        query = query.where(
            Payment.payment_date >= datetime.combine(
                from_date,
                datetime.min.time()
            )
        )

    if to_date:
        query = query.where(
            Payment.payment_date <= datetime.combine(
                to_date,
                datetime.max.time()
            )
        )

    result = await db.execute(query)
    payments = result.scalars().all()

    cash_total = 0
    upi_total = 0
    card_total = 0
    credit_total = 0

    for payment in payments:

        for item in (payment.payment_breakdown or []):

            method = item.get(
                "payment_method",
                ""
            ).lower()

            amount = float(
                item.get(
                    "payment_amount",
                    0
                )
            )

            if method == "cash":
                cash_total += amount

            elif method == "upi":
                upi_total += amount

            elif method == "card":
                card_total += amount

            elif method == "credit":
                credit_total += amount

    total_collection = (
        cash_total +
        upi_total +
        card_total +
        credit_total
    )

    return {
        "cash_total": round(cash_total, 2),
        "upi_total": round(upi_total, 2),
        "card_total": round(card_total, 2),
        "credit_total": round(credit_total, 2),
        "total_collection": round(total_collection, 2)
    }
    await Cache.set(cache_key, result, expire=21600)
    return result


from datetime import datetime, date
from sqlalchemy import select

from app.accounts.payment.model import Payment
from app.accounts.branch.model import Branch


async def payment_method_totals_all_branches_service(
    db,
    client_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
):
    cache_key = f"report:all:payment_totals_all:{client_id}:{from_date or 'all'}_{to_date or 'all'}"
    cached = await Cache.get(cache_key)
    if cached:
        return cached
    query = (
        select(Payment)
        .join(
            Branch,
            Payment.branch_id == Branch.id
        )
        .where(
            Branch.client_id == client_id
        )
    )

    if from_date:
        query = query.where(
            Payment.payment_date >= datetime.combine(
                from_date,
                datetime.min.time()
            )
        )

    if to_date:
        query = query.where(
            Payment.payment_date <= datetime.combine(
                to_date,
                datetime.max.time()
            )
        )

    result = await db.execute(query)
    payments = result.scalars().all()

    cash_total = 0
    upi_total = 0
    card_total = 0
    credit_total = 0

    for payment in payments:

        for item in (payment.payment_breakdown or []):

            method = (
                item.get(
                    "payment_method",
                    ""
                )
                .strip()
                .lower()
            )

            amount = float(
                item.get(
                    "payment_amount",
                    0
                )
            )

            if method == "cash":
                cash_total += amount

            elif method == "upi":
                upi_total += amount

            elif method == "card":
                card_total += amount

            elif method == "credit":
                credit_total += amount

    total_collection = (
        cash_total +
        upi_total +
        card_total +
        credit_total
    )

    return {
        "cash_total": round(cash_total, 2),
        "upi_total": round(upi_total, 2),
        "card_total": round(card_total, 2),
        "credit_total": round(credit_total, 2),
        "total_collection": round(total_collection, 2)
    }
    await Cache.set(cache_key, result, expire=21600)
    return result