# app/accounts/crm/customer_history/service.py

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.customer.model import Customer
from app.accounts.crm.customer_history.model import (
    CustomerVisitHistory,
)


# ==========================================================
# CREATE VISIT HISTORY
# ==========================================================

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
    payment_method: Optional[str] = None,
    table_name: Optional[str] = None,
    visit_type: Optional[str] = None,
    current_spend: float = 0,
    visit_date: Optional[datetime] = None,
) -> CustomerVisitHistory:

    visit = CustomerVisitHistory(
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,

        order_id=order_id,
        bill_id=bill_id,

        visit_date=(
            visit_date
            or datetime.utcnow()
        ),

        total_amount=max(
            float(total_amount or 0),
            0.0,
        ),

        discount=max(
            float(discount or 0),
            0.0,
        ),

        tax=max(
            float(tax or 0),
            0.0,
        ),

        # Historical snapshot.
        current_spend=max(
            float(current_spend or 0),
            0.0,
        ),

        payment_method=payment_method,
        table_name=table_name,
        visit_type=visit_type,
    )

    db.add(visit)

    await db.flush()

    return visit


# ==========================================================
# GET CUSTOMER VISITS
# ==========================================================

async def get_customer_visits(
    db: AsyncSession,
    customer_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
):

    stmt = select(
        CustomerVisitHistory
    )

    if (
        customer_id is not None
        and customer_id > 0
    ):
        stmt = stmt.where(
            CustomerVisitHistory.customer_id
            == customer_id
        )

    stmt = (
        stmt
        .order_by(
            CustomerVisitHistory.visit_date.desc(),
            CustomerVisitHistory.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)

    return result.scalars().all()


# ==========================================================
# GET CUSTOMER VISIT STATS
# ==========================================================

async def get_visit_stats(
    db: AsyncSession,
    customer_id: int,
) -> dict:
    """
    Customer statistics.

    total_spend:
        Customer.total_spend
        Lifetime spend. NEVER reset by redemption.

    current_spend:
        Customer.current_spend
        Accumulated spend since last successful redemption.

    redeem_count:
        Customer.redeem_count
        Successful full redemption count.

    IMPORTANT:
        current_spend is NOT calculated from history rows.

        History current_spend is only a historical snapshot.
    """

    # ======================================================
    # HISTORY STATISTICS
    # ======================================================

    history_stmt = select(
        func.count(
            CustomerVisitHistory.id
        ),

        func.coalesce(
            func.sum(
                CustomerVisitHistory.total_amount
            ),
            0,
        ),

        func.coalesce(
            func.avg(
                CustomerVisitHistory.total_amount
            ),
            0,
        ),

        func.coalesce(
            func.max(
                CustomerVisitHistory.total_amount
            ),
            0,
        ),

        func.max(
            CustomerVisitHistory.visit_date
        ),
    ).where(
        CustomerVisitHistory.customer_id
        == customer_id
    )

    history_result = await db.execute(
        history_stmt
    )

    (
        total_visits,
        history_total_spend,
        average_spend,
        highest_bill,
        last_visit,
    ) = history_result.one()

    # ======================================================
    # CUSTOMER LIVE VALUES
    # ======================================================

    customer_stmt = select(
        Customer.current_spend,
        Customer.total_spend,
        Customer.redeem_count,
    ).where(
        Customer.id == customer_id
    )

    customer_result = await db.execute(
        customer_stmt
    )

    customer_row = (
        customer_result.one_or_none()
    )

    if customer_row:

        current_spend = float(
            customer_row[0] or 0
        )

        lifetime_total_spend = float(
            customer_row[1] or 0
        )

        redeem_count = int(
            customer_row[2] or 0
        )

    else:

        current_spend = 0.0
        lifetime_total_spend = 0.0
        redeem_count = 0

    # ======================================================
    # RETURN
    # ======================================================

    return {
        "total_visits": int(
            total_visits or 0
        ),

        "total_spend": round(
            lifetime_total_spend,
            2,
        ),

        "current_spend": round(
            current_spend,
            2,
        ),

        "redeem_count": redeem_count,

        "average_spend": round(
            float(average_spend or 0),
            2,
        ),

        "highest_bill": round(
            float(highest_bill or 0),
            2,
        ),

        "last_visit": last_visit,
    }


# ==========================================================
# UPDATE CUSTOMER STATISTICS AFTER SUCCESSFUL BILL
# ==========================================================

async def update_customer_stats(
    db: AsyncSession,
    customer: Customer,
    visit: CustomerVisitHistory,
):
    """
    Called ONLY after a successful bill.

    Rules:

        total_spend
            += bill amount

        current_spend
            += bill amount

        redeem_count
            unchanged

        history.current_spend
            = post-bill customer.current_spend

    Example:

        Before bill:

            current_spend = 2360

        Bill:

            amount = 2832

        After:

            current_spend = 5192
            total_spend += 2832

        History row:

            current_spend = 5192
    """

    # ======================================================
    # BILL AMOUNT
    # ======================================================

    amount = float(
        visit.total_amount or 0
    )

    if amount < 0:
        amount = 0.0

    amount = round(
        amount,
        2,
    )

    # ======================================================
    # TOTAL ORDERS
    # ======================================================

    customer.total_orders = (
        int(
            customer.total_orders or 0
        )
        + 1
    )

    # ======================================================
    # TOTAL VISITS
    # ======================================================

    customer.total_visits = (
        int(
            customer.total_visits or 0
        )
        + 1
    )

    # ======================================================
    # LIFETIME TOTAL SPEND
    # ======================================================

    old_total_spend = float(
        customer.total_spend or 0
    )

    customer.total_spend = round(
        old_total_spend + amount,
        2,
    )

    # ======================================================
    # CURRENT SPEND
    # ======================================================

    old_current_spend = float(
        customer.current_spend or 0
    )

    customer.current_spend = round(
        old_current_spend + amount,
        2,
    )

    # ======================================================
    # AVERAGE ORDER VALUE
    # ======================================================

    if customer.total_orders > 0:

        customer.average_order_value = round(
            float(
                customer.total_spend or 0
            )
            / customer.total_orders,
            2,
        )

    else:

        customer.average_order_value = 0.0

    # ======================================================
    # LAST ORDER
    # ======================================================

    customer.last_order_amount = amount

    customer.last_visit_at = (
        visit.visit_date
    )

    customer.last_order_id = (
        visit.order_id
    )

    # ======================================================
    # FIRST VISIT
    # ======================================================

    if not customer.first_visit_at:

        customer.first_visit_at = (
            visit.visit_date
        )

    # ======================================================
    # HISTORY SNAPSHOT
    # ======================================================
    #
    # VERY IMPORTANT
    #
    # This is NOT a live reference.
    #
    # We copy the current value into the history row.
    #
    # Example:
    #
    # customer.current_spend = 5192
    #
    # visit.current_spend = 5192
    #
    # Later redemption:
    #
    # customer.current_spend = 0
    #
    # This history row MUST remain 5192.
    #

    visit.current_spend = round(
        float(
            customer.current_spend or 0
        ),
        2,
    )

    # ======================================================
    # EXPLICITLY MARK BOTH OBJECTS DIRTY
    # ======================================================

    db.add(customer)
    db.add(visit)

    # ======================================================
    # FLUSH
    # ======================================================

    await db.flush()

    return customer


# ==========================================================
# REDEEM CURRENT SPEND
# ==========================================================

async def redeem_current_spend(
    db: AsyncSession,
    customer: Customer,
):
    """
    FULL CURRENT SPEND REDEMPTION.

    Rules:

        current_spend > 0
            redeem_count += 1
            current_spend = 0

        current_spend <= 0
            reject redemption

        total_spend
            NEVER changes

        CustomerVisitHistory
            NEVER changes
    """

    # ======================================================
    # READ CURRENT SPEND
    # ======================================================

    current_spend = float(
        customer.current_spend or 0
    )

    # ======================================================
    # VALIDATION
    # ======================================================

    if current_spend <= 0:

        raise ValueError(
            "Customer has no current spend available for redemption."
        )

    # ======================================================
    # INCREMENT REDEMPTION COUNT
    # ======================================================

    customer.redeem_count = (
        int(
            customer.redeem_count or 0
        )
        + 1
    )

    # ======================================================
    # RESET CURRENT SPEND
    # ======================================================

    customer.current_spend = 0.0

    # ======================================================
    # IMPORTANT
    # ======================================================
    #
    # DO NOT TOUCH:
    #
    # customer.total_spend
    #
    # DO NOT TOUCH:
    #
    # CustomerVisitHistory
    #

    db.add(customer)

    await db.flush()

    return customer


# ==========================================================
# MANUAL RESET
# ==========================================================

async def reset_current_spend_after_full_redemption(
    db: AsyncSession,
    customer: Customer,
):
    """
    Backward-compatible manual reset.

    This does NOT increment redeem_count.

    Normal loyalty redemption MUST use:

        redeem_current_spend()
    """

    customer.current_spend = 0.0

    db.add(customer)

    await db.flush()

    return customer