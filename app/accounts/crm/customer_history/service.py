from datetime import datetime, date, time, timedelta

from fastapi import HTTPException
from sqlalchemy import select, func, desc

from app.accounts.customer.model import Customer
from app.accounts.crm.customer_history.model import CustomerVisitHistory


# ==========================================================
# INTERNAL
# ==========================================================

async def refresh_customer_summary(
    customer_id: int,
    db
):
    customer = await db.get(
        Customer,
        customer_id
    )

    if not customer:
        return

    result = await db.execute(
        select(CustomerVisitHistory).where(
            CustomerVisitHistory.customer_id == customer_id,
            CustomerVisitHistory.visit_status == "Completed"
        )
    )

    visits = result.scalars().all()

    customer.total_visits = len(visits)
    customer.total_orders = len(visits)

    customer.total_spend = sum(
        i.total_amount for i in visits
    )

    customer.average_order_value = (
        int(customer.total_spend / len(visits))
        if visits else 0
    )

    customer.last_order_amount = (
        visits[-1].total_amount
        if visits else 0
    )

    if visits:

        customer.first_visit_at = min(
            x.visit_date for x in visits
        )

        customer.last_visit_at = max(
            x.visit_date for x in visits
        )

        customer.last_order_id = visits[-1].order_id

    else:

        customer.first_visit_at = None
        customer.last_visit_at = None
        customer.last_order_id = None

    await db.commit()


# ==========================================================
# CREATE
# ==========================================================

async def create_customer_visit_service(
    payload,
    db
):

    customer = await db.get(
        Customer,
        payload.customer_id
    )

    if not customer:
        raise HTTPException(
            404,
            "Customer not found."
        )

    visit = CustomerVisitHistory(

        customer_id=customer.id,

        order_id=payload.order_id,

        bill_id=payload.bill_id,

        client_id=customer.client_id,

        branch_id=customer.branch_id,

        visit_type=payload.visit_type,

        visit_channel=payload.visit_channel,

        visit_status="Completed",

        visit_date=datetime.utcnow(),

        payment_method=payload.payment_method,

        table_name=payload.table_name,

        served_by=payload.served_by,

        total_amount=payload.total_amount,

        discount=payload.discount,

        tax=payload.tax,

        notes=payload.notes

    )

    db.add(visit)

    await db.commit()

    await db.refresh(visit)

    await refresh_customer_summary(
        customer.id,
        db
    )

    return visit


# ==========================================================
# GET SINGLE
# ==========================================================

async def get_customer_visit_service(
    visit_id: int,
    db
):

    visit = await db.get(
        CustomerVisitHistory,
        visit_id
    )

    if not visit:
        raise HTTPException(
            404,
            "Visit not found."
        )

    return visit


# ==========================================================
# UPDATE
# ==========================================================

async def update_customer_visit_service(
    visit_id: int,
    payload,
    db
):

    visit = await db.get(
        CustomerVisitHistory,
        visit_id
    )

    if not visit:
        raise HTTPException(
            404,
            "Visit not found."
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():

        setattr(
            visit,
            key,
            value
        )

    await db.commit()

    await db.refresh(visit)

    return visit


# ==========================================================
# DELETE
# ==========================================================

async def delete_customer_visit_service(
    visit_id: int,
    db
):

    visit = await db.get(
        CustomerVisitHistory,
        visit_id
    )

    if not visit:
        raise HTTPException(
            404,
            "Visit not found."
        )

    customer_id = visit.customer_id

    await db.delete(visit)

    await db.commit()

    await refresh_customer_summary(
        customer_id,
        db
    )

    return {
        "message": "Visit deleted successfully."
    }


# ==========================================================
# CUSTOMER TIMELINE
# ==========================================================

async def get_customer_timeline_service(
    customer_id: int,
    db
):

    result = await db.execute(

        select(CustomerVisitHistory)

        .where(
            CustomerVisitHistory.customer_id == customer_id
        )

        .order_by(
            desc(CustomerVisitHistory.visit_date)
        )

    )

    return result.scalars().all()


# ==========================================================
# RECENT VISITS
# ==========================================================

async def get_recent_visits_service(
    db,
    limit: int = 20
):

    result = await db.execute(

        select(CustomerVisitHistory)

        .order_by(
            desc(CustomerVisitHistory.visit_date)
        )

        .limit(limit)

    )

    return result.scalars().all()


# ==========================================================
# TODAY VISITS
# ==========================================================

async def get_today_visits_service(
    db
):

    start = datetime.combine(
        date.today(),
        time.min
    )

    end = datetime.combine(
        date.today(),
        time.max
    )

    result = await db.execute(

        select(CustomerVisitHistory)

        .where(
            CustomerVisitHistory.visit_date >= start,
            CustomerVisitHistory.visit_date <= end
        )

        .order_by(
            desc(CustomerVisitHistory.visit_date)
        )

    )

    return result.scalars().all()


# ==========================================================
# ANALYTICS
# ==========================================================

async def get_customer_analytics_service(
    customer_id: int,
    db
):

    result = await db.execute(

        select(CustomerVisitHistory)

        .where(
            CustomerVisitHistory.customer_id == customer_id
        )

    )

    visits = result.scalars().all()

    if not visits:

        raise HTTPException(
            404,
            "No visit history found."
        )

    amounts = [
        i.total_amount
        for i in visits
    ]

    return {

        "total_visits": len(visits),

        "total_orders": len(visits),

        "total_spend": sum(amounts),

        "average_order_value": int(
            sum(amounts) / len(amounts)
        ),

        "highest_bill": max(amounts),

        "lowest_bill": min(amounts),

        "first_visit": min(
            x.visit_date for x in visits
        ),

        "last_visit": max(
            x.visit_date for x in visits
        )

    }


# ==========================================================
# REPEAT CUSTOMERS
# ==========================================================

async def get_repeat_customers_service(
    db
):

    result = await db.execute(

        select(Customer)

        .where(
            Customer.total_visits > 1
        )

        .order_by(
            desc(Customer.total_visits)
        )

    )

    return result.scalars().all()


# ==========================================================
# INACTIVE CUSTOMERS
# ==========================================================

async def get_inactive_customers_service(
    days: int,
    db
):

    limit_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(

        select(Customer)

        .where(
            Customer.last_visit_at < limit_date
        )

        .order_by(
            Customer.last_visit_at
        )

    )

    return result.scalars().all()