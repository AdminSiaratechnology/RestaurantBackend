from typing import Optional
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.customer_history.model import CustomerVisitHistory


# =========================================================
# CREATE
# =========================================================
   
async def create_visit_history(
    db: AsyncSession,
    *,
    customer_id: int,
    client_id: int,
    branch_id: int,
    order_id: Optional[int] = None,
    bill_id: Optional[int] = None,
    total_amount: float = 0,
    discount: float = 0,
    tax: float = 0,
    net_amount: float = 0,
    payment_method: Optional[str] = None,
    table_name: Optional[str] = None,
    visit_type: Optional[str] = None,
    visit_date: Optional[datetime] = None,
) -> CustomerVisitHistory:

    visit = CustomerVisitHistory(
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
        order_id=order_id,
        bill_id=bill_id,
        visit_date=visit_date or datetime.utcnow(),
        total_amount=total_amount,
        discount=discount,
        tax=tax,
        payment_method=payment_method,
        table_name=table_name,
        visit_type=visit_type,
    )

    db.add(visit)
    await db.flush()

    return visit


# =========================================================
# READ
# =========================================================

async def get_customer_visits(
    db: AsyncSession,
    customer_id: int,
    limit: int = 50,
    offset: int = 0,
):

    stmt = (
        select(CustomerVisitHistory)
        .where(CustomerVisitHistory.customer_id == customer_id)
        .order_by(CustomerVisitHistory.visit_date.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)

    return result.scalars().all()


async def get_visit_stats(
    db: AsyncSession,
    customer_id: int,
) -> dict:

    stmt = select(
        func.count(CustomerVisitHistory.id),
        func.coalesce(func.sum(CustomerVisitHistory.total_amount), 0),
        func.coalesce(func.avg(CustomerVisitHistory.total_amount), 0),
        func.coalesce(func.max(CustomerVisitHistory.total_amount), 0),
        func.max(CustomerVisitHistory.visit_date),
    ).where(
        CustomerVisitHistory.customer_id == customer_id
    )

    result = await db.execute(stmt)

    total_visits, total_spend, avg_spend, highest_bill, last_visit = result.one()

    return {
        "total_visits": int(total_visits or 0),
        "total_spend": round(float(total_spend or 0), 2),
        "average_spend": round(float(avg_spend or 0), 2),
        "highest_bill": round(float(highest_bill or 0), 2),
        "last_visit": last_visit,
    }

# =========================================================
# UPDATE CUSTOMER AGGREGATE STATS
# =========================================================

async def update_customer_stats(
    db: AsyncSession,
    customer,
    visit: CustomerVisitHistory,
):

    customer.total_orders += 1
    customer.total_visits += 1
    customer.total_spend += visit.total_amount  or 0
    customer.average_order_value = round(
        customer.total_spend / customer.total_orders,
        2,
    )
    customer.last_order_amount = visit.total_amount
    customer.last_visit_at = visit.visit_date

    if not customer.first_visit_at:
        customer.first_visit_at = visit.visit_date

    await db.flush()

    return customer