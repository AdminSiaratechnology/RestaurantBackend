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

        # Send FCM Push Notifications
        try:
            from app.accounts.notification.service import NotificationService
            from app.accounts.notification.model import NotificationType

            if dto.points_earned > 0:
                await NotificationService.send_loyalty_update(
                    db=context.db,
                    customer_id=customer.id,
                    client_id=customer.client_id,
                    title="Loyalty Points Updated",
                    body=f"You earned {dto.points_earned} loyalty points on your visit!",
                    data={"points_earned": str(dto.points_earned), "total_spend": str(customer.total_spend)},
                    event_type=NotificationType.POINTS_EARNED.value,
                )
            if dto.rank_upgraded:
                await NotificationService.send_loyalty_update(
                    db=context.db,
                    customer_id=customer.id,
                    client_id=customer.client_id,
                    title="New Loyalty Level 🎉",
                    body=f"Congratulations! You are now a {dto.new_rank} member!",
                    data={"new_rank": str(dto.new_rank)},
                    event_type=NotificationType.RANK_UPGRADE.value,
                )
            if dto.wallet_credited > 0:
                await NotificationService.send_loyalty_update(
                    db=context.db,
                    customer_id=customer.id,
                    client_id=customer.client_id,
                    title="Wallet Cashback Credited",
                    body=f"Cashback of {dto.wallet_credited} has been credited to your wallet!",
                    data={"wallet_credited": str(dto.wallet_credited)},
                    event_type=NotificationType.WALLET_CREDITED.value,
                )
        except Exception as fcm_e:
            crm_logger.warning(f"Failed to dispatch FCM loyalty notification: {fcm_e}")

        context.dto.metadata["notifications_sent"] = notifications_sent
