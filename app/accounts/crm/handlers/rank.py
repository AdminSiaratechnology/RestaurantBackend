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

        if previous_rank == new_rank:
            crm_logger.info(
                f"[{self.name}] Customer #{customer.id} "
                f"remains {new_rank}."
            )
            return

        customer.current_rank = new_rank
        context.dto.rank_upgraded = True

        await context.db.flush()

        crm_logger.info(
            f"[{self.name}] Customer #{customer.id} "
            f"Rank: {previous_rank} -> {new_rank} "
            f"(Spend={total_spend})"
        )