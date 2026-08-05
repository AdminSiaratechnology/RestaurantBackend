"""
app/accounts/crm/rank_rules/service.py

Business Logic Service Layer for Branch-wise Customer Rank Rules.
Extracted client context safely from auth dictionary {"user": user, "role": role}.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.branch.model import Branch
from app.accounts.crm.rank_rules.repository import RankRuleRepository
from app.accounts.crm.rank_rules.schema import (
    PaginationResponse,
    RankRuleBase,
    RankRuleCreate,
    RankRuleListResponse,
    RankRuleResponse,
    RankRuleUpdate,
)
from app.accounts.crm.utils.logger import crm_logger
from app.accounts.enum import UserRole


def _extract_client_id(current_user) -> int:
    """
    Extracts client_id from get_current_user auth structure:
    {"user": user_obj, "role": UserRole}
    """
    if isinstance(current_user, dict):
        role = current_user.get("role")
        user = current_user.get("user")

        if role == UserRole.CLIENT:
            return user.id
        elif role == UserRole.STAFF:
            return user.client_id
        elif role in (UserRole.SUPER_ADMIN, UserRole.PARTNER):
            return getattr(user, "client_id", getattr(user, "id", None))
        else:
            raise HTTPException(status_code=403, detail="Access denied.")

    # Direct attribute fallback if object passed
    if hasattr(current_user, "client_id"):
        return current_user.client_id
    if hasattr(current_user, "id"):
        return current_user.id

    raise HTTPException(status_code=403, detail="Access denied.")


async def create_rank_rule_service(
    db: AsyncSession,
    current_user,
    payload: RankRuleCreate,
) -> RankRuleResponse:
    """
    Creates a new branch rank rule.
    Validates branch existence, client authorization, and rejects creation if active rule exists.
    """
    repo = RankRuleRepository(db)
    client_id = _extract_client_id(current_user)

    branch = await db.get(Branch, payload.branch_id)
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found.",
        )

    if branch.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this branch.",
        )

    if await repo.rule_exists(
        client_id=client_id,
        branch_id=payload.branch_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active rank rule already exists for Branch #{payload.branch_id}.",
        )

    rule = await repo.create_rule(
        client_id=client_id,
        branch_id=payload.branch_id,
        bronze_min=payload.bronze_min,
        bronze_max=payload.bronze_max,
        silver_min=payload.silver_min,
        silver_max=payload.silver_max,
        gold_min=payload.gold_min,
    )

    crm_logger.info(
        f"[RankRules] Created rank rule for Branch #{payload.branch_id} (Client #{client_id}): "
        f"Bronze [₹{rule.bronze_min}-₹{rule.bronze_max}], Silver [₹{rule.silver_min}-₹{rule.silver_max}], Gold [₹{rule.gold_min}+]"
    )

    return RankRuleResponse.model_validate(rule)


async def get_rank_rule_service(
    db: AsyncSession,
    current_user,
    branch_id: int,
) -> RankRuleResponse:
    """
    Fetches configured thresholds for a branch.
    """
    repo = RankRuleRepository(db)
    client_id = _extract_client_id(current_user)

    rule = await repo.get_branch_rule_for_client(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active rank rule not found for Branch #{branch_id}.",
        )

    return RankRuleResponse.model_validate(rule)


async def update_rank_rule_service(
    db: AsyncSession,
    current_user,
    branch_id: int,
    payload: RankRuleUpdate,
) -> RankRuleResponse:
    """
    Updates active rank rule for a branch after validating merged threshold bounds.
    """
    repo = RankRuleRepository(db)
    client_id = _extract_client_id(current_user)

    rule = await repo.get_branch_rule_for_client(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active rank rule not found for Branch #{branch_id}.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    merged = {
        "bronze_min": update_data.get("bronze_min", rule.bronze_min),
        "bronze_max": update_data.get("bronze_max", rule.bronze_max),
        "silver_min": update_data.get("silver_min", rule.silver_min),
        "silver_max": update_data.get("silver_max", rule.silver_max),
        "gold_min": update_data.get("gold_min", rule.gold_min),
    }

    try:
        RankRuleBase(**merged)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        )

    updated = await repo.update_rule(
        rule=rule,
        update_data=update_data,
    )

    crm_logger.info(
        f"[RankRules] Updated rank rule for Branch #{branch_id}: "
        f"Bronze [₹{updated.bronze_min}-₹{updated.bronze_max}], Silver [₹{updated.silver_min}-₹{updated.silver_max}], Gold [₹{updated.gold_min}+]"
    )

    return RankRuleResponse.model_validate(updated)


async def delete_rank_rule_service(
    db: AsyncSession,
    current_user,
    branch_id: int,
) -> RankRuleResponse:
    """
    Soft-deletes the rank rule for a branch (sets is_active = False).
    """
    repo = RankRuleRepository(db)
    client_id = _extract_client_id(current_user)

    rule = await repo.get_branch_rule_for_client(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active rank rule not found for Branch #{branch_id}.",
        )

    deleted = await repo.delete_rule(rule)

    crm_logger.info(
        f"[RankRules] Soft-deleted rank rule for Branch #{branch_id}."
    )

    return RankRuleResponse.model_validate(deleted)


async def list_rank_rules_service(
    db: AsyncSession,
    current_user,
    branch_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
) -> RankRuleListResponse:
    """
    Lists branch rank rules belonging to the authenticated user's client.
    """
    repo = RankRuleRepository(db)
    client_id = _extract_client_id(current_user)

    items, total, total_pages = await repo.list_rules(
        client_id=client_id,
        branch_id=branch_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return RankRuleListResponse(
        items=[RankRuleResponse.model_validate(i) for i in items],
        pagination=PaginationResponse(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )