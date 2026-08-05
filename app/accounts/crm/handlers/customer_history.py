"""
app/accounts/crm/handlers/customer_history.py

Step 1 Handler: Creates Customer Visit History entry upon bill completion.
"""

from datetime import datetime
from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger


class CustomerHistoryHandler(BaseCRMHandler):
    """
    Step 1: Creates an immutable CustomerVisitHistory record.
    """

    @property
    def name(self) -> str:
        return "CustomerHistoryHandler"

    async def process(self, context: CRMContext) -> None:
        from app.accounts.crm.customer_history.model import CustomerVisitHistory

        if not context.customer or not context.bill:
            crm_logger.warning(f"[{self.name}] Skipping: Customer or Bill missing in context.")
            return

        visit = CustomerVisitHistory(
            customer_id=context.customer.id,
            order_id=context.event.order_id,
            bill_id=context.event.bill_id,
            client_id=context.event.client_id,
            branch_id=context.event.branch_id,
            visit_date=context.bill.billed_at or datetime.utcnow(),
            total_amount=float(context.bill.grand_total or 0.0),
            discount=float(context.bill.discount_amount or 0.0),
            tax=float(context.bill.tax_total or 0.0),
            payment_method=context.bill.payment_method or "UNKNOWN",
            visit_type=context.bill.order_type or "Dine-In"
        )

        context.db.add(visit)
        await context.db.flush()
        crm_logger.info(f"[{self.name}] Created visit history record for Customer #{context.customer.id}")
