# app/accounts/crm/customer_history/checkout_service.py

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.customer.service import (
    find_or_create_customer,
)

from app.accounts.crm.customer_history.service import (
    create_visit_history,
    update_customer_stats,
)

logger = logging.getLogger(__name__)


# ==========================================================
# HANDLE CUSTOMER + VISIT
# ==========================================================

async def handle_customer_and_visit(
    db: AsyncSession,
    *,
    client_id: int,
    branch_id: int,
    branch_name: str,
    order_id: Optional[int] = None,
    bill_id: Optional[int] = None,
    total_amount: float = 0,
    discount: float = 0,
    tax: float = 0,
    payment_method: Optional[str] = None,
    table_name: Optional[str] = None,
    visit_type: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
):
    """
    Resolve customer, create visit history,
    and update customer statistics.

    BUSINESS RULES:

        total_spend:
            Lifetime spend.
            NEVER reset.

        current_spend:
            Accumulated spend after last redemption.

        redeem_count:
            Successful full redemption count.

        visit.current_spend:
            Historical post-bill snapshot.
    """

    logger.info(
        "[CheckoutService] handle_customer_and_visit "
        "triggered for Bill #%s, Order #%s, Phone='%s', Name='%s'",
        bill_id,
        order_id,
        customer_phone,
        customer_name,
    )

    # ======================================================
    # RESOLVE / CREATE CUSTOMER
    # ======================================================

    customer, created = (
        await find_or_create_customer(
            db=db,
            client_id=client_id,
            branch_id=branch_id,
            branch_name=branch_name,
            name=customer_name or "Walk-in Guest",
            phone=customer_phone,
            email=customer_email,
        )
    )

    # ======================================================
    # CUSTOMER NOT FOUND
    # ======================================================

    if not customer:

        logger.error(
            "[CheckoutService] Failed to resolve "
            "or create customer for Bill #%s",
            bill_id,
        )

        return None

    logger.info(
        "[CheckoutService] Resolved Customer #%s "
        "('%s', Phone='%s') [New=%s]",
        customer.id,
        customer.name,
        customer.phone,
        created,
    )

    # ======================================================
    # CREATE VISIT
    # ======================================================
    #
    # Temporary value.
    #
    # update_customer_stats() immediately replaces
    # this with the POST-BILL current_spend.
    #

    visit = await create_visit_history(
        db=db,

        customer_id=customer.id,

        client_id=client_id,

        branch_id=branch_id,

        order_id=order_id,

        bill_id=bill_id,

        total_amount=total_amount,

        discount=discount,

        tax=tax,

        payment_method=payment_method,

        table_name=table_name,

        visit_type=visit_type,

        current_spend=0.0,
    )

    # ======================================================
    # UPDATE CUSTOMER STATISTICS
    # ======================================================

    await update_customer_stats(
        db=db,
        customer=customer,
        visit=visit,
    )

    logger.info(
        "[CheckoutService] Customer #%s statistics updated. "
        "Total Spend=₹%.2f, Current Spend=₹%.2f, "
        "Redeem Count=%s, Visit Snapshot=₹%.2f",
        customer.id,

        float(
            customer.total_spend or 0
        ),

        float(
            customer.current_spend or 0
        ),

        int(
            customer.redeem_count or 0
        ),

        float(
            visit.current_spend or 0
        ),
    )

    return customer