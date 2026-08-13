"""
app/accounts/crm/customer_history/service.py

Customer Visit History + Customer Spend Statistics

BUSINESS RULES
--------------

1. total_spend
   - Customer ka lifetime spend.
   - Kabhi reset nahi hoga.
   - Loyalty redemption ka total_spend par koi effect nahi.

2. current_spend
   - Last successful redemption ke baad ka spend.
   - New successful bill par increase hoga.
   - Successful redemption par 0 ho jayega.

3. redeem_count
   - Customer ke successful full redemptions ka count.
   - Initial value = 0.
   - Sirf tab +1 hoga jab current_spend > 0.
   - Successful redemption ke baad current_spend = 0.

4. CustomerVisitHistory.current_spend
   - Visit ke time ka historical snapshot hai.
   - Redemption ke baad old history rows modify nahi hongi.

5. total_spend
   - Redemption ke waqt kabhi subtract/reset nahi hoga.
"""


from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.customer.model import Customer
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

        total_amount=float(
            total_amount or 0
        ),

        discount=float(
            discount or 0
        ),

        tax=float(
            tax or 0
        ),

        # Historical snapshot only.
        current_spend=float(
            current_spend or 0
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
            CustomerVisitHistory.visit_date.desc()
        )
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)

    return result.scalars().all()


# ==========================================================
# VISIT STATISTICS
# ==========================================================

async def get_visit_stats(
    db: AsyncSession,
    customer_id: int,
) -> dict:
    """
    Return customer visit statistics.

    total_spend:
        Customer.total_spend

    current_spend:
        Customer.current_spend

    redeem_count:
        Customer.redeem_count

    IMPORTANT:
    current_spend is NEVER calculated by summing
    visit-history snapshots.
    """

    # ======================================================
    # HISTORY STATISTICS
    # ======================================================

    stmt = select(
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

    result = await db.execute(stmt)

    (
        total_visits,
        history_total_spend,
        average_spend,
        highest_bill,
        last_visit,
    ) = result.one()

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

        "average_spend": round(
            float(average_spend or 0),
            2,
        ),

        "highest_bill": round(
            float(highest_bill or 0),
            2,
        ),

        "last_visit": last_visit,

        "redeem_count": redeem_count,
    }


# ==========================================================
# UPDATE CUSTOMER STATISTICS AFTER BILL
# ==========================================================

async def update_customer_stats(
    db: AsyncSession,
    customer: Customer,
    visit: CustomerVisitHistory,
):
    """
    Update customer statistics after successful bill.

    BILL LOGIC:

        total_spend
            += bill amount

        current_spend
            += bill amount

    redeem_count is NOT changed here.

    redeem_count changes ONLY during
    successful redemption.
    """

    amount = float(
        visit.total_amount or 0
    )

    # ======================================================
    # SAFETY
    # ======================================================

    if amount < 0:
        amount = 0.0

    # ======================================================
    # TOTAL ORDERS
    # ======================================================

    customer.total_orders = (
        int(
            customer.total_orders or 0
        ) + 1
    )

    # ======================================================
    # TOTAL VISITS
    # ======================================================

    customer.total_visits = (
        int(
            customer.total_visits or 0
        ) + 1
    )

    # ======================================================
    # LIFETIME TOTAL SPEND
    # ======================================================

    customer.total_spend = round(
        float(
            customer.total_spend or 0
        ) + amount,
        2,
    )

    # ======================================================
    # CURRENT SPEND
    # ======================================================

    customer.current_spend = round(
        float(
            customer.current_spend or 0
        ) + amount,
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
    # IMPORTANT:
    #
    # Save current_spend AFTER this bill.
    #
    # This is a historical value.
    #
    # If later:
    #
    # customer.current_spend = 0
    #
    # this history row remains unchanged.
    #

    visit.current_spend = round(
        float(
            customer.current_spend or 0
        ),
        2,
    )

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

    BUSINESS RULE:

    If current_spend > 0:

        redeem_count += 1
        current_spend = 0

    If current_spend <= 0:

        redemption is rejected
        redeem_count remains unchanged

    total_spend is NEVER changed.

    Example:

        current_spend = 5000
        redeem_count = 0

        Redeem

        current_spend = 0
        redeem_count = 1
        total_spend = unchanged

    Next:

        bill = 2000

        current_spend = 2000
        redeem_count = 1

    Redeem:

        current_spend = 0
        redeem_count = 2
    """

    # ======================================================
    # READ CURRENT SPEND
    # ======================================================

    current_spend = float(
        customer.current_spend or 0
    )

    # ======================================================
    # CONDITION
    # ======================================================
    #
    # Count MUST increase only when
    # current_spend actually contains value.
    #

    if current_spend <= 0:

        raise ValueError(
            "Customer has no current spend available for redemption."
        )

    # ======================================================
    # STORE PREVIOUS COUNT
    # ======================================================
    #
    # This guarantees that every successful
    # redemption increments the previous value by 1.
    #

    previous_redeem_count = int(
        customer.redeem_count or 0
    )

    # ======================================================
    # INCREMENT REDEEM COUNT
    # ======================================================

    customer.redeem_count = (
        previous_redeem_count + 1
    )

    # ======================================================
    # RESET CURRENT SPEND
    # ======================================================
    #
    # After successful redeem:
    #
    # current_spend -> 0
    #

    customer.current_spend = 0.0

    # ======================================================
    # IMPORTANT
    # ======================================================
    #
    # DO NOT CHANGE:
    #
    # customer.total_spend
    #
    # Lifetime spend must remain untouched.
    #

    await db.flush()

    return customer


# ==========================================================
# RESET CURRENT SPEND AFTER FULL REDEMPTION
# ==========================================================

async def reset_current_spend_after_full_redemption(
    db: AsyncSession,
    customer: Customer,
):
    """
    Backward-compatible helper.

    IMPORTANT:
    Normal redemption should use
    redeem_current_spend().

    This function only resets current_spend.
    It does NOT increment redeem_count.

    Use this only when you intentionally need
    a manual reset outside the redemption flow.
    """

    customer.current_spend = 0.0

    await db.flush()

    return customer