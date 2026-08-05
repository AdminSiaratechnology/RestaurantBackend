"""
app/accounts/crm/handlers/coupon.py

Step 6b Handler: Checks qualification and auto-issues coupons.
"""

from datetime import datetime, timedelta
from multiprocessing import context
import uuid
from sqlalchemy import select
from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.utils.logger import crm_logger
# from app.accounts.crm.campaigns.model import Coupon
from app.accounts.offer.model import Offer
from app.accounts.crm.campaigns.model import CustomerCoupon

class CouponHandler(BaseCRMHandler):
    """
    Step 6b: Evaluates criteria for rank upgrade coupons, milestone spend coupons, etc.
    """

    @property
    def name(self) -> str:
        return "CouponHandler"

    async def process(self, context: CRMContext) -> None:
        customer = context.customer

        if not customer:
            crm_logger.warning(f"[{self.name}] Skipping: Customer missing.")
            return

        issued_offers = []

        if context.dto.rank_upgraded:

            stmt = (
                select(Offer)
                .where(
                    Offer.branch_id == customer.branch_id,
                    Offer.is_active.is_(True),
                )
                .order_by(Offer.created_at.desc())
            )

            result = await context.db.execute(stmt)
            offer = result.scalar_one_or_none()

            if not offer:
                crm_logger.warning(
                    f"[{self.name}] No active offer found for Branch #{customer.branch_id}"
                )
                return

            customer_offer = CustomerCoupon(
                customer_id=customer.id,
                offer_id=offer.id,
                status="ISSUED",
                issued_reason=f"Achieved new rank: {context.dto.new_rank}",
            )

            context.db.add(customer_offer)
            await context.db.flush()

            issued_offers.append(offer.offer_name)

            crm_logger.info(
                f"[{self.name}] Assigned Offer '{offer.offer_name}' "
                f"to Customer #{customer.id}"
            )

        context.dto.coupons_issued.extend(issued_offers)