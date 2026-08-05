"""
app/accounts/crm/rank_rules/repository.py

Repository layer for CRM Branch Rank Rules.
"""

from math import ceil
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.branch.model import Branch
from app.accounts.crm.rank_rules.model import CRMBranchRankRule


class RankRuleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_branch_rule(
        self,
        client_id: int,
        branch_id: int,
        is_active_only: bool = True,
    ) -> Optional[CRMBranchRankRule]:
        """
        Get a rank rule for a branch that belongs to the given client.
        """

        stmt = (
            select(CRMBranchRankRule)
            .join(
                Branch,
                Branch.id == CRMBranchRankRule.branch_id,
            )
            .where(
                CRMBranchRankRule.branch_id == branch_id,
                Branch.client_id == client_id,
            )
        )

        if is_active_only:
            stmt = stmt.where(CRMBranchRankRule.is_active.is_(True))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()



    

    async def rule_exists(
        self,
        client_id: int,
        branch_id: int,
    ) -> bool:
        rule = await self.get_branch_rule(
            client_id=client_id,
            branch_id=branch_id,
            is_active_only=True,
        )
        return rule is not None

    async def create_rule(
        self,
        branch_id: int,
        bronze_max: float,
        silver_min: float,
        silver_max: float,
        gold_min: float,
    ) -> CRMBranchRankRule:

        rule = CRMBranchRankRule(
            branch_id=branch_id,
            bronze_max=bronze_max,
            silver_min=silver_min,
            silver_max=silver_max,
            gold_min=gold_min,
            is_active=True,
        )

        self.db.add(rule)

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    async def update_rule(
        self,
        rule: CRMBranchRankRule,
        update_data: dict,
    ) -> CRMBranchRankRule:

        for key, value in update_data.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    async def delete_rule(
        self,
        rule: CRMBranchRankRule,
    ) -> CRMBranchRankRule:

        rule.is_active = False

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    async def list_rules(
        self,
        client_id: int,
        branch_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CRMBranchRankRule], int, int]:

        stmt = (
            select(CRMBranchRankRule)
            .join(
                Branch,
                Branch.id == CRMBranchRankRule.branch_id,
            )
            .where(
                Branch.client_id == client_id,
            )
        )

        if branch_id is not None:
            stmt = stmt.where(
                CRMBranchRankRule.branch_id == branch_id
            )

        if is_active is not None:
            stmt = stmt.where(
                CRMBranchRankRule.is_active == is_active
            )

        count_stmt = (
            select(func.count())
            .select_from(stmt.subquery())
        )

        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            stmt.order_by(CRMBranchRankRule.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        items = (
            await self.db.execute(stmt)
        ).scalars().all()

        total_pages = ceil(total / page_size) if total else 0

        return items, total, total_pages