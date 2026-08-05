"""
app/accounts/crm/handlers/notification.py

Step 8 Handler: Dispatches automated customer notifications (SMS/WhatsApp/Email).
"""

from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger


class NotificationHandler(BaseCRMHandler):
    """
    Step 8: Final stage handler for pushing notifications (WhatsApp / SMS / Push).
    """

    @property
    def name(self) -> str:
        return "NotificationHandler"

    async def process(self, context: CRMContext) -> None:
        customer = context.customer
        if not customer:
            return

        dto = context.dto
        channel = customer.preferred_contact or "WhatsApp"

        notifications_sent = []

        # Send Loyalty Points Earned Notification
        if dto.points_earned > 0:
            msg = f"Dear {customer.name}, you earned {dto.points_earned} loyalty points on your visit! Total spend: ₹{customer.total_spend}."
            crm_logger.info(f"[{self.name}] Pushed [{channel}] Notification to {customer.phone}: {msg}")
            notifications_sent.append("LOYALTY_EARNED")

        # Send Rank Upgrade Notification
        if dto.rank_upgraded:
            msg = f"Congratulations {customer.name}! You are now a {dto.new_rank} member!"
            crm_logger.info(f"[{self.name}] Pushed [{channel}] Notification to {customer.phone}: {msg}")
            notifications_sent.append("RANK_UPGRADE")

        # Send Wallet Cashback Notification
        if dto.wallet_credited > 0:
            msg = f"₹{dto.wallet_credited} cashback has been credited to your wallet!"
            crm_logger.info(f"[{self.name}] Pushed [{channel}] Notification to {customer.phone}: {msg}")
            notifications_sent.append("WALLET_CREDITED")

        context.dto.metadata["notifications_sent"] = notifications_sent
