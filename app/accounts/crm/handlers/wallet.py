"""
app/accounts/crm/handlers/wallet.py

Step 6a Handler: Manages Customer Wallet transactions & cashback credits.
"""

from sqlalchemy import select
from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger


class WalletHandler(BaseCRMHandler):
    """
    Step 6a: Checks cashback eligibility and processes wallet updates.
    """

    @property
    def name(self) -> str:
        return "WalletHandler"

    async def process(self, context: CRMContext) -> None:
        from app.accounts.crm.wallet.model import CustomerWalletAccount, WalletTransaction

        customer = context.customer
        bill = context.bill

        if not customer or not bill:
            crm_logger.warning(f"[{self.name}] Skipping: Customer or Bill missing.")
            return

        grand_total = float(bill.grand_total or 0.0)

        # Example rule: 5% cashback on bills above ₹2,000 for Silver/Gold members
        cashback_amount = 0.0
        if grand_total >= 2000.0 and customer.current_rank in ["Silver", "Gold"]:
            cashback_amount = round(grand_total * 0.05, 2)

        if cashback_amount <= 0:
            crm_logger.info(f"[{self.name}] No wallet cashback eligible for Bill #{bill.id}.")
            return

        context.dto.wallet_credited = cashback_amount

        # Fetch or create CustomerWalletAccount
        stmt = select(CustomerWalletAccount).where(CustomerWalletAccount.customer_id == customer.id)
        res = await context.db.execute(stmt)
        wallet = res.scalar_one_or_none()

        if not wallet:
            wallet = CustomerWalletAccount(
                customer_id=customer.id,
                client_id=context.event.client_id,
                balance=0.0,
                total_recharged=0.0,
                total_spent=0.0
            )
            context.db.add(wallet)
            await context.db.flush()

        wallet.balance += cashback_amount
        wallet.total_recharged += cashback_amount
        await context.db.flush()

        # Record Wallet Transaction
        tx = WalletTransaction(
            account_id=wallet.id,
            customer_id=customer.id,
            bill_id=bill.id,
            transaction_type="CASHBACK",
            amount=cashback_amount,
            balance_after=wallet.balance,
            remarks=f"5% Cashback on Bill #{bill.id} (Rank: {customer.current_rank})"
        )
        context.db.add(tx)
        await context.db.flush()

        crm_logger.info(
            f"[{self.name}] Credited ₹{cashback_amount} cashback to Customer #{customer.id}'s wallet. "
            f"New Wallet Balance: ₹{wallet.balance}"
        )
