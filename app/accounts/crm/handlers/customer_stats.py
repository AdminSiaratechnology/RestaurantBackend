"""
app/accounts/crm/handlers/customer_stats.py

Step 2 Handler: Updates Customer aggregate statistics.
"""

from datetime import datetime
from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger


class CustomerStatsHandler(BaseCRMHandler):
    """
    Step 2: Updates aggregated customer analytics attributes.
    """

    @property
    def name(self) -> str:
        return "CustomerStatsHandler"

    async def process(self, context: CRMContext) -> None:
        customer = context.customer
        bill = context.bill

        if not customer or not bill:
            crm_logger.warning(f"[{self.name}] Skipping: Customer or Bill missing in context.")
            return

        bill_amount = int(bill.grand_total or 0)

        # Update Visit Counts & Spend
        customer.total_visits = (customer.total_visits or 0) + 1
        customer.total_orders = (customer.total_orders or 0) + 1
        customer.total_spend = (customer.total_spend or 0) + bill_amount

        # Calculate Average Order Value
        if customer.total_orders > 0:
            customer.average_order_value = int(customer.total_spend / customer.total_orders)

        # Update Last Visit Details
        now = datetime.utcnow()
        if not customer.first_visit_at:
            customer.first_visit_at = now
        customer.last_visit_at = now
        customer.last_order_amount = bill_amount
        customer.last_order_id = bill.order_id
        customer.branch_id = context.event.branch_id

        await context.db.flush()
        crm_logger.info(
            f"[{self.name}] Customer #{customer.id} stats updated: "
            f"Visits={customer.total_visits}, TotalSpend=₹{customer.total_spend}, AOV=₹{customer.average_order_value}"
        )
