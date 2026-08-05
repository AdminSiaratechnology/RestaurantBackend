"""
app/accounts/crm/handlers/loyalty.py

Step 4 & 5 Handler: Calculates Loyalty Points & creates Loyalty Transaction.
"""

from sqlalchemy import select
from app.accounts.crm.config import crm_config
from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger


class LoyaltyHandler(BaseCRMHandler):
    """
    Step 4 & 5: Computes loyalty points earned and logs transaction history.
    """

    @property
    def name(self) -> str:
        return "LoyaltyHandler"

    async def process(self, context: CRMContext) -> None:
        from app.accounts.crm.loyalty.model import CustomerLoyaltyAccount, LoyaltyTransaction

        customer = context.customer
        bill = context.bill

        if not customer or not bill:
            crm_logger.warning(f"[{self.name}] Skipping: Customer or Bill missing.")
            return

        grand_total = float(bill.grand_total or 0.0)
        loyalty_cfg = crm_config.loyalty

        # Calculate points earned
        points_earned = (grand_total / loyalty_cfg.POINTS_PER_AMOUNT) * loyalty_cfg.POINTS_EARNED_PER_UNIT
        points_earned = round(points_earned, 2)

        if points_earned <= 0:
            crm_logger.info(f"[{self.name}] No loyalty points earned for Bill #{bill.id}.")
            return

        context.dto.points_earned = points_earned

        # Fetch or create CustomerLoyaltyAccount
        stmt = select(CustomerLoyaltyAccount).where(CustomerLoyaltyAccount.customer_id == customer.id)
        res = await context.db.execute(stmt)
        account = res.scalar_one_or_none()

        if not account:
            account = CustomerLoyaltyAccount(
                customer_id=customer.id,
                client_id=context.event.client_id,
                total_points_earned=0.0,
                total_points_redeemed=0.0,
                current_points_balance=0.0
            )
            context.db.add(account)
            await context.db.flush()

        # Update account balances
        account.total_points_earned += points_earned
        account.current_points_balance += points_earned
        await context.db.flush()

        # Insert transaction log
        transaction = LoyaltyTransaction(
            account_id=account.id,
            customer_id=customer.id,
            bill_id=bill.id,
            transaction_type="EARNED",
            points=points_earned,
            balance_after=account.current_points_balance,
            description=f"Earned {points_earned} points on Bill #{bill.id} (Amount: ₹{grand_total})"
        )
        context.db.add(transaction)
        await context.db.flush()

        crm_logger.info(
            f"[{self.name}] Awarded {points_earned} points to Customer #{customer.id}. "
            f"New Balance: {account.current_points_balance}"
        )
