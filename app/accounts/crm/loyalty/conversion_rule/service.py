"""
app/accounts/crm/loyalty/conversion_rule/service.py

Services for branch-wise loyalty conversion rules.
"""

from typing import Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.branch.model import Branch
from app.accounts.crm.loyalty.conversion_rule.model import (
    LoyaltyConversionRule,
)


# ============================================================
# GET ACTIVE RULE
# ============================================================


async def get_active_rule(
    db: AsyncSession,
    *,
    client_id: int,
    branch_id: int,
) -> Optional[LoyaltyConversionRule]:

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.client_id == client_id,
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
    client_id: int,
    branch_id: int,
) -> Optional[LoyaltyConversionRule]:

    stmt = (
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.client_id == client_id,
            LoyaltyConversionRule.branch_id == branch_id,
        )
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()


# ============================================================
# GET OR CREATE LOYALTY CONVERSION RULE
# ============================================================


async def get_or_create_loyalty_conversion_rule(
    db: AsyncSession,
    *,
    client_id: int,
    branch_id: int,
) -> LoyaltyConversionRule:
    """
    Get existing active loyalty conversion rule for client_id + branch_id.
    If none exists, validate branch ownership and create default rule:
        10 points = ₹5, is_active = True
    """
    # 1. Validate branch ownership
    branch = await db.get(Branch, branch_id)
    if not branch or branch.client_id != client_id:
        raise HTTPException(
            status_code=400,
            detail="The selected branch does not belong to this customer’s client.",
        )

    # 2. Check for active rule
    rule = await get_active_rule(db, client_id=client_id, branch_id=branch_id)
    if rule:
        return rule

    # 3. Check for existing rule (inactive)
    any_rule = await get_rule(db, client_id=client_id, branch_id=branch_id)
    if any_rule:
        any_rule.is_active = True
        await db.commit()
        await db.refresh(any_rule)
        return any_rule

    # 4. Create default rule for this client + branch
    rule = LoyaltyConversionRule(
        client_id=client_id,
        branch_id=branch_id,
        points_required=10.0,
        rupee_value=5.0,
        is_active=True,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


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

    branch = await db.get(Branch, branch_id)
    if not branch or branch.client_id != client_id:
        raise HTTPException(
            status_code=400,
            detail="The selected branch does not belong to this customer’s client.",
        )

    existing_rule = await get_rule(db, client_id=client_id, branch_id=branch_id)

    if existing_rule:
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
    client_id: int,
    branch_id: int,
    points_required: float | None = None,
    rupee_value: float | None = None,
    is_active: bool | None = None,
) -> LoyaltyConversionRule:

    branch = await db.get(Branch, branch_id)
    if not branch or branch.client_id != client_id:
        raise HTTPException(
            status_code=400,
            detail="The selected branch does not belong to this customer’s client.",
        )

    rule = await get_rule(db, client_id=client_id, branch_id=branch_id)

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
    client_id: int,
    branch_id: int,
) -> Optional[LoyaltyConversionRule]:

    rule = await get_rule(db, client_id=client_id, branch_id=branch_id)

    if rule is None:
        return None

    rule.is_active = False

    await db.commit()
    await db.refresh(rule)

    return rule