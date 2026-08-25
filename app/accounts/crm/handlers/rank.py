"""
app/accounts/crm/handlers/rank.py

Step 3 Handler: Recalculates Customer Rank (Bronze, Silver, Gold)
based on Branch-wise Rank Rules.
"""

from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.rank_rules.repository import RankRuleRepository
from app.accounts.crm.utils.logger import crm_logger


class RankHandler(BaseCRMHandler):
    """
    Step 3:
    Calculates customer rank using the active Branch Rank Rule.
    Customer in CRM event pipeline is trusted; fetches branch rule directly.
    """

    @property
    def name(self) -> str:
        return "RankHandler"

    async def process(self, context: CRMContext) -> None:
        customer = context.customer

        if not customer:
            crm_logger.warning(
                f"[{self.name}] Customer not found. Skipping."
            )
            return

        previous_rank = customer.current_rank or "Bronze"
        context.dto.previous_rank = previous_rank

        repo = RankRuleRepository(context.db)

        rule = await repo.get_branch_rule(
            client_id=customer.client_id or context.event.client_id,
            branch_id=customer.branch_id,
            is_active_only=True,
        )

        if not rule:
            crm_logger.warning(
                f"[{self.name}] No active Rank Rule found "
                f"for Branch #{customer.branch_id}. Skipping rank calculation."
            )
            context.dto.new_rank = previous_rank
            return

        total_spend = float(customer.total_spend or 0)

        if total_spend >= rule.gold_min:
            new_rank = "Gold"
        elif total_spend >= rule.silver_min:
            new_rank = "Silver"
        else:
            new_rank = "Bronze"

        context.dto.new_rank = new_rank

        from app.accounts.customer.service import determine_customer_type
        from app.accounts.customer.model import CustomerTypeEnum

        customer.current_rank = new_rank
        customer.customer_type = determine_customer_type(
            rank=customer.current_rank,
            visit_count=customer.total_visits or 0,
        )
        customer.is_vip = (
            customer.customer_type == CustomerTypeEnum.VIP
        )

        if previous_rank == new_rank:
            crm_logger.info(
                f"[{self.name}] Customer #{customer.id} "
                f"remains {new_rank} (type={customer.customer_type.value})."
            )
            await context.db.flush()
            return

        context.dto.rank_upgraded = True

        await context.db.flush()

        crm_logger.info(
            f"[{self.name}] Customer #{customer.id} "
            f"Rank: {previous_rank} -> {new_rank} "
            f"(Type={customer.customer_type.value}, Spend={total_spend})"
        )