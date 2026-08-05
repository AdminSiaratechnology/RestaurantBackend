"""
app/accounts/crm/services/crm_service.py

Database & Entity Hydration Service for CRM Workers.
Fetches additional entity information (Bill, Customer, Order) from DB dynamically
instead of clogging Redis queue with heavy payloads.
"""

from typing import Tuple, Optional, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

if TYPE_CHECKING:
    from app.accounts.bill.model import Bill
    from app.accounts.customer.model import Customer
    from app.accounts.order.model import Order

from app.accounts.crm.utils.logger import crm_logger


class CRMDataService:
    """
    Central database entity loader for CRM context.
    """

    @staticmethod
    async def load_crm_entities(
        db: AsyncSession,
        bill_id: int,
        customer_id: int,
        order_id: int
    ) -> Tuple[Optional["Bill"], Optional["Customer"], Optional["Order"]]:
        """
        Loads Bill, Customer, and Order entities from the DB dynamically.
        Includes fallback resolution to find/create customer if customer_id was 0 or unlinked.
        """
        from app.accounts.bill.model import Bill
        from app.accounts.customer.model import Customer
        from app.accounts.order.model import Order

        # 1. Fetch Bill
        bill_stmt = select(Bill).where(Bill.id == bill_id)
        bill_res = await db.execute(bill_stmt)
        bill = bill_res.scalar_one_or_none()

        # 2. Fetch Customer by passed customer_id
        customer = None
        if customer_id and customer_id > 0:
            cust_stmt = select(Customer).where(Customer.id == customer_id)
            cust_res = await db.execute(cust_stmt)
            customer = cust_res.scalar_one_or_none()

        # 3. Fallback: check bill's customer_id if not found yet
        if not customer and bill and bill.customer_id:
            cust_stmt = select(Customer).where(Customer.id == bill.customer_id)
            cust_res = await db.execute(cust_stmt)
            customer = cust_res.scalar_one_or_none()

        # 4. Fallback: find or create customer using bill details or branch Walk-in Guest fallback
        if not customer and bill:
            try:
                from app.accounts.customer.service import find_or_create_customer
                customer, _created = await find_or_create_customer(
                    db=db,
                    client_id=bill.client_id,
                    branch_id=bill.branch_id,
                    branch_name="",
                    name=bill.customer_name or "Walk-in Guest",
                    phone=bill.customer_phone,
                    email=None
                )
                if customer and bill:
                    bill.customer_id = customer.id
                    await db.flush()
            except Exception as err:
                crm_logger.warning(f"Fallback customer creation failed: {err}")

        # 5. Fetch Order
        order_stmt = select(Order).where(Order.id == order_id)
        order_res = await db.execute(order_stmt)
        order = order_res.scalar_one_or_none()

        if not bill:
            crm_logger.warning(f"Bill #{bill_id} not found in database.")
        if not customer:
            crm_logger.warning(f"Customer for Bill #{bill_id} could not be resolved.")
        if not order:
            crm_logger.warning(f"Order #{order_id} not found in database.")

        return bill, customer, order
