"""
app/accounts/crm/rank_rules/router.py

FastAPI REST Router for Branch-wise Customer Rank Rule Management.
Uses access_one dependency to restrict access to CLIENT and STAFF roles.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.accounts.crm.rank_rules import service
from app.accounts.crm.rank_rules.schema import (
    RankRuleCreate,
    RankRuleListResponse,
    RankRuleResponse,
    RankRuleUpdate,
)
from app.accounts.deps import access_one
from app.db.config import SessionDep

router = APIRouter(
    prefix="/crm/rank-rules",
    tags=["CRM Branch Rank Rules"],
)


@router.post(
    "",
    response_model=RankRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Rank Rule for a Branch",
)
async def create_rank_rule(
    payload: RankRuleCreate,
    db: SessionDep,
    current=Depends(access_one),
):
    """
    Creates a spend-based rank threshold rule for a branch.
    Rejects creation if an active rule already exists for the branch.
    """
    return await service.create_rank_rule_service(
        db=db,
        current_user=current,
        payload=payload,
    )


@router.get(
    "/{branch_id}",
    response_model=RankRuleResponse,
    summary="Get Active Rank Rule for a Branch",
)
async def get_rank_rule(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one),
):
    """
    Fetches the configured rank thresholds for a specific branch.
    """
    return await service.get_rank_rule_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
    )


@router.put(
    "/{branch_id}",
    response_model=RankRuleResponse,
    summary="Update Active Rank Rule for a Branch",
)
async def update_rank_rule(
    branch_id: int,
    payload: RankRuleUpdate,
    db: SessionDep,
    current=Depends(access_one),
):
    """
    Updates the active spend-based rank thresholds for a branch.
    """
    return await service.update_rank_rule_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
        payload=payload,
    )


@router.delete(
    "/{branch_id}",
    response_model=RankRuleResponse,
    summary="Soft Delete Active Rank Rule for a Branch",
)
async def delete_rank_rule(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one),
):
    """
    Soft-deletes the rank rule for a branch by setting is_active = False.
    """
    return await service.delete_rank_rule_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
    )


@router.get(
    "",
    response_model=RankRuleListResponse,
    summary="List Branch Rank Rules with Filters & Pagination",
)
async def list_rank_rules(
    db: SessionDep,
    current=Depends(access_one),
    branch_id: Optional[int] = Query(None, description="Filter by Branch ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Lists branch rank rules with optional filtering and pagination.
    """
    return await service.list_rank_rules_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )