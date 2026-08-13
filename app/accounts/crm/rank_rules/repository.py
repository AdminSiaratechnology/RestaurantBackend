"""
app/accounts/crm/rank_rules/repository.py

Repository layer for CRM Branch Rank Rules.
"""

from math import ceil
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.rank_rules.model import CRMBranchRankRule


class RankRuleRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========================================================
    # GET SINGLE BRANCH RULE
    # ========================================================

    async def get_branch_rule(
        self,
        client_id: int,
        branch_id: int,
        is_active_only: bool = True,
    ) -> Optional[CRMBranchRankRule]:

        stmt = (
            select(CRMBranchRankRule)
            .where(
                CRMBranchRankRule.client_id == client_id,
                CRMBranchRankRule.branch_id == branch_id,
            )
        )

        if is_active_only:
            stmt = stmt.where(
                CRMBranchRankRule.is_active.is_(True)
            )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none()

    # ========================================================
    # CHECK ACTIVE RULE
    # ========================================================

    async def rule_exists(
        self,
        client_id: int,
        branch_id: int,
    ) -> bool:

        stmt = (
            select(CRMBranchRankRule.id)
            .where(
                CRMBranchRankRule.client_id == client_id,
                CRMBranchRankRule.branch_id == branch_id,
                CRMBranchRankRule.is_active.is_(True),
            )
            .limit(1)
        )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none() is not None

    # ========================================================
    # CREATE
    # ========================================================

    async def create_rule(
        self,
        client_id: int,
        branch_id: int,
        bronze_max: float,
        silver_min: float,
        silver_max: float,
        gold_min: float,
        bronze_pts: float = 1.0,
        silver_pts: float = 2.0,
        gold_pts: float = 3.0,
    ) -> CRMBranchRankRule:

        rule = CRMBranchRankRule(
            client_id=client_id,
            branch_id=branch_id,

            bronze_min=0.0,
            bronze_max=bronze_max,

            silver_min=silver_min,
            silver_max=silver_max,

            gold_min=gold_min,

            bronze_pts=bronze_pts,
            silver_pts=silver_pts,
            gold_pts=gold_pts,

            is_active=True,
        )

        self.db.add(rule)

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    # ========================================================
    # UPDATE
    # ========================================================

    async def update_rule(
        self,
        rule: CRMBranchRankRule,
        update_data: dict,
    ) -> CRMBranchRankRule:

        allowed_fields = {
            "bronze_max",
            "silver_min",
            "silver_max",
            "gold_min",
            "bronze_pts",
            "silver_pts",
            "gold_pts",
            "is_active",
        }

        for key, value in update_data.items():

            if key in allowed_fields:
                setattr(
                    rule,
                    key,
                    value,
                )

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    # ========================================================
    # SOFT DELETE
    # ========================================================

    async def delete_rule(
        self,
        rule: CRMBranchRankRule,
    ) -> CRMBranchRankRule:

        rule.is_active = False

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    # ========================================================
    # LIST
    # ========================================================

    async def list_rules(
        self,
        client_id: int,
        branch_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[
        List[CRMBranchRankRule],
        int,
        int,
    ]:

        stmt = (
            select(CRMBranchRankRule)
            .where(
                CRMBranchRankRule.client_id == client_id,
            )
        )

        # ====================================================
        # BRANCH FILTER
        #
        # None = ALL BRANCHES
        # ====================================================

        if branch_id is not None:

            stmt = stmt.where(
                CRMBranchRankRule.branch_id == branch_id
            )

        # ====================================================
        # ACTIVE FILTER
        # ====================================================

        if is_active is not None:

            stmt = stmt.where(
                CRMBranchRankRule.is_active == is_active
            )

        # ====================================================
        # COUNT
        # ====================================================

        count_stmt = (
            select(func.count())
            .select_from(stmt.subquery())
        )

        count_result = await self.db.execute(
            count_stmt
        )

        total = count_result.scalar() or 0

        # ====================================================
        # PAGINATION
        # ====================================================

        stmt = (
            stmt
            .order_by(
                CRMBranchRankRule.created_at.desc()
            )
            .offset(
                (page - 1) * page_size
            )
            .limit(page_size)
        )

        result = await self.db.execute(stmt)

        items = result.scalars().all()

        total_pages = (
            ceil(total / page_size)
            if total
            else 0
        )

        return (
            items,
            total,
            total_pages,
        )