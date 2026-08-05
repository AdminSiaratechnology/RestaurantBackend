"""
app/accounts/crm/customer_history/checkout_service.py

Single entrypoint for customer identification and visit history creation during bill completion.
"""

from typing import Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.customer.service import find_or_create_customer
from app.accounts.crm.customer_history.service import (
    create_visit_history,
    update_customer_stats,
)

logger = logging.getLogger(__name__)


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
    Single entrypoint executed upon successful bill payment completion.

    1. Resolves/creates customer (Walk-in Guest fallback if phone/email omitted).
    2. Inserts CustomerVisitHistory entry into database.
    3. Updates customer statistics.
    """
    logger.info(
        f"[CheckoutService] handle_customer_and_visit triggered for Bill #{bill_id}, "
        f"Order #{order_id}, Phone: '{customer_phone}', Name: '{customer_name}'"
    )

    customer, created = await find_or_create_customer(
        db=db,
        client_id=client_id,
        branch_id=branch_id,
        branch_name=branch_name,
        name=customer_name or "Walk-in Guest",
        phone=customer_phone,
        email=customer_email,
    )

    if not customer:
        logger.error(f"[CheckoutService] Failed to resolve or create customer for Bill #{bill_id}")
        return None

    logger.info(
        f"[CheckoutService] Resolved Customer #{customer.id} ('{customer.name}', Phone: '{customer.phone}') "
        f"[New: {created}]"
    )

    visit = await create_visit_history(
        db,
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
    )

    logger.info(
        f"[CheckoutService] Successfully created CustomerVisitHistory for Customer #{customer.id}, "
        f"Bill #{bill_id}, Total Amount: ₹{total_amount}"
    )

    await update_customer_stats(db, customer=customer, visit=visit)

    return customer