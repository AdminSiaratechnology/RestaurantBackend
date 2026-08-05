"""
app/accounts/crm/events/dispatcher.py

CRM Event Dispatcher implementation.
Sequentially dispatches events to registered Single Responsibility Handlers.
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.handlers.customer_history import CustomerHistoryHandler
from app.accounts.crm.handlers.customer_stats import CustomerStatsHandler
from app.accounts.crm.handlers.rank import RankHandler
from app.accounts.crm.handlers.loyalty import LoyaltyHandler
from app.accounts.crm.handlers.wallet import WalletHandler
from app.accounts.crm.handlers.coupon import CouponHandler
from app.accounts.crm.handlers.campaign import CampaignHandler
from app.accounts.crm.handlers.notification import NotificationHandler
from app.accounts.crm.events.schema import BillCompletedEvent
from app.accounts.crm.services.crm_service import CRMDataService
from app.accounts.crm.utils.logger import crm_logger


class CRMEventDispatcher:
    """
    Orchestrates the sequence of CRM Handlers:
    Step 1: CustomerHistoryHandler
    Step 2: CustomerStatsHandler
    Step 3: RankHandler
    Step 4 & 5: LoyaltyHandler
    Step 6a: WalletHandler
    Step 6b: CouponHandler
    Step 7: CampaignHandler
    Step 8: NotificationHandler
    """

    def __init__(self, handlers: List[BaseCRMHandler] = None):
        if handlers is None:
            # Default pipeline ordered sequentially as specified in requirements
            self.handlers: List[BaseCRMHandler] = [
                CustomerHistoryHandler(),
                CustomerStatsHandler(),
                RankHandler(),
                LoyaltyHandler(),
                WalletHandler(),
                CouponHandler(),
                CampaignHandler(),
                NotificationHandler(),
            ]
        else:
            self.handlers = handlers

    def register_handler(self, handler: BaseCRMHandler) -> None:
        """
        Dynamically registers a new CRM handler (Open-Closed Principle).
        """
        self.handlers.append(handler)
        crm_logger.info(f"[Dispatcher] Registered new handler: {handler.name}")

    async def dispatch(self, event: BillCompletedEvent, db_session: AsyncSession) -> CRMContext:
        """
        Hydrates DB entities and runs all active handlers sequentially.
        """
        crm_logger.info(
            f"[Dispatcher] Starting CRM pipeline for Bill #{event.bill_id}, Customer #{event.customer_id}"
        )

        # Hydrate entities from database
        bill, customer, order = await CRMDataService.load_crm_entities(
            db=db_session,
            bill_id=event.bill_id,
            customer_id=event.customer_id,
            order_id=event.order_id
        )

        context = CRMContext(
            event=event,
            db=db_session,
            bill=bill,
            customer=customer,
            order=order
        )

        # Execute registered handlers sequentially
        for handler in self.handlers:
            if handler.is_enabled:
                crm_logger.info(f"[Dispatcher] Executing [{handler.name}]...")
                try:
                    await handler.process(context)
                except Exception as exc:
                    crm_logger.error(f"[Dispatcher] Error in [{handler.name}]: {exc}", exc_info=True)
                    raise exc

        crm_logger.info(f"[Dispatcher] Successfully completed CRM pipeline for Bill #{event.bill_id}")
        return context
