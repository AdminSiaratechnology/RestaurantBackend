"""
app/accounts/crm/loyalty/conversion_rule/service.py

Services for branch-wise loyalty conversion rules.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.loyalty.conversion_rule.model import (
    LoyaltyConversionRule,
)


# ============================================================
# GET ACTIVE RULE
# ============================================================


async def get_active_rule(
    db: AsyncSession,
    *,
    branch_id: int,
) -> Optional[LoyaltyConversionRule]:

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.branch_id == branch_id,
            LoyaltyConversionRule.is_active.is_(True),
        )
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()


# ============================================================
# GET ANY RULE
# ============================================================


async def get_rule(
    db: AsyncSession,
    *,
    branch_id: int,
) -> Optional[LoyaltyConversionRule]:

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.branch_id == branch_id
        )
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()


# ============================================================
# CREATE / REPLACE RULE
# ============================================================


async def create_rule(
    db: AsyncSession,
    *,
    client_id: int,
    branch_id: int,
    points_required: float,
    rupee_value: float,
    is_active: bool,
) -> LoyaltyConversionRule:

    # Because branch_id is unique,
    # a branch can have only one rule.

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.branch_id == branch_id
        )
    )

    result = await db.execute(stmt)

    existing_rule = result.scalar_one_or_none()

    if existing_rule:

        existing_rule.client_id = client_id
        existing_rule.points_required = points_required
        existing_rule.rupee_value = rupee_value
        existing_rule.is_active = is_active

        await db.commit()

        await db.refresh(existing_rule)

        return existing_rule

    rule = LoyaltyConversionRule(
        client_id=client_id,
        branch_id=branch_id,
        points_required=points_required,
        rupee_value=rupee_value,
        is_active=is_active,
    )

    db.add(rule)

    await db.commit()

    await db.refresh(rule)

    return rule


# ============================================================
# UPDATE RULE
# ============================================================


async def update_rule(
    db: AsyncSession,
    *,
    branch_id: int,
    client_id: int = 1,
    points_required: float | None = None,
    rupee_value: float | None = None,
    is_active: bool | None = None,
) -> LoyaltyConversionRule:

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.branch_id == branch_id
        )
    )

    result = await db.execute(stmt)

    rule = result.scalar_one_or_none()

    if rule is None:
        rule = LoyaltyConversionRule(
            client_id=client_id,
            branch_id=branch_id,
            points_required=points_required if points_required is not None else 10.0,
            rupee_value=rupee_value if rupee_value is not None else 5.0,
            is_active=is_active if is_active is not None else True,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    if points_required is not None:
        rule.points_required = points_required

    if rupee_value is not None:
        rule.rupee_value = rupee_value

    if is_active is not None:
        rule.is_active = is_active

    await db.commit()

    await db.refresh(rule)

    return rule


# ============================================================
# DEACTIVATE RULE
# ============================================================


async def deactivate_rule(
    db: AsyncSession,
    *,
    branch_id: int,
) -> Optional[LoyaltyConversionRule]:

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.branch_id == branch_id
        )
    )

    result = await db.execute(stmt)

    rule = result.scalar_one_or_none()

    if rule is None:
        return None

    rule.is_active = False

    await db.commit()

    await db.refresh(rule)

    return rule