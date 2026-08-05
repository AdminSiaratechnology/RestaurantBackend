"""
app/accounts/crm/handlers/campaign.py

Step 7 Handler: Evaluates eligibility and triggers Campaign Events.
"""

from datetime import datetime, date
from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger


class CampaignHandler(BaseCRMHandler):
    """
    Step 7: Checks for special automated campaign trigger events:
    - New Rank Achieved
    - Upcoming Birthday / Anniversary
    - Loyalty / Wallet balance milestones
    """

    @property
    def name(self) -> str:
        return "CampaignHandler"

    async def process(self, context: CRMContext) -> None:
        from app.accounts.crm.campaigns.model import CampaignLog

        customer = context.customer
        if not customer:
            crm_logger.warning(f"[{self.name}] Skipping: Customer missing.")
            return

        today = date.today()
        campaign_events = []

        # 1. Rank Upgrade Event
        if context.dto.rank_upgraded:
            event_name = f"CAMPAIGN_RANK_UPGRADE_{context.dto.new_rank.upper()}"
            campaign_log = CampaignLog(
                customer_id=customer.id,
                client_id=context.event.client_id,
                trigger_event=event_name,
                channel=customer.preferred_contact or "WHATSAPP",
                status="TRIGGERED",
                payload=f"Congratulations! You have achieved {context.dto.new_rank} status."
            )
            context.db.add(campaign_log)
            campaign_events.append(event_name)

        # 2. Birthday Event
        if customer.dob and customer.dob.month == today.month and customer.dob.day == today.day and not customer.birthday_wish_sent:
            event_name = "CAMPAIGN_BIRTHDAY_SPECIAL"
            customer.birthday_wish_sent = True
            campaign_log = CampaignLog(
                customer_id=customer.id,
                client_id=context.event.client_id,
                trigger_event=event_name,
                channel=customer.preferred_contact or "WHATSAPP",
                status="TRIGGERED",
                payload=f"Happy Birthday {customer.name}! Enjoy a special treat on your next visit."
            )
            context.db.add(campaign_log)
            campaign_events.append(event_name)

        # 3. Anniversary Event
        if customer.anniversary and customer.anniversary.month == today.month and customer.anniversary.day == today.day and not customer.anniversary_wish_sent:
            event_name = "CAMPAIGN_ANNIVERSARY_SPECIAL"
            customer.anniversary_wish_sent = True
            campaign_log = CampaignLog(
                customer_id=customer.id,
                client_id=context.event.client_id,
                trigger_event=event_name,
                channel=customer.preferred_contact or "WHATSAPP",
                status="TRIGGERED",
                payload=f"Happy Anniversary {customer.name}!"
            )
            context.db.add(campaign_log)
            campaign_events.append(event_name)

        await context.db.flush()
        context.dto.campaign_events_triggered.extend(campaign_events)

        if campaign_events:
            crm_logger.info(
                f"[{self.name}] Triggered {len(campaign_events)} campaign events for Customer #{customer.id}: {campaign_events}"
            )
