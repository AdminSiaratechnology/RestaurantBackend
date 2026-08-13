"""
app/accounts/crm/rank_rules/router.py

FastAPI REST Router for Branch-wise Customer Rank Rules.
"""

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

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


# ============================================================
# CREATE
# ============================================================

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
    client_id: Optional[int] = Query(
        None,
        description="Filter/specify Client ID",
    ),
):

    return await service.create_rank_rule_service(
        db=db,
        current_user=current,
        payload=payload,
    )


# ============================================================
# LIST
# ============================================================

@router.get(
    "",
    response_model=RankRuleListResponse,
    summary="List Branch Rank Rules",
)
async def list_rank_rules(
    db: SessionDep,
    current=Depends(access_one),

    client_id: Optional[int] = Query(
        None,
        description="Filter by Client ID",
    ),

    # IMPORTANT:
    # Accept both:
    # ?branch_id=3
    # ?branch_id=all
    branch_id: Optional[str] = Query(
        None,
        description='Branch ID or "all"',
    ),

    is_active: Optional[bool] = Query(
        None,
        description="Filter by active status",
    ),

    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Items per page",
    ),
):

    # ========================================================
    # PARSE BRANCH ID
    # ========================================================

    parsed_branch_id: Optional[int] = None

    if branch_id is not None:

        value = branch_id.strip().lower()

        # ----------------------------------------------------
        # ALL BRANCHES
        # ----------------------------------------------------

        if value == "all":

            parsed_branch_id = None

        # ----------------------------------------------------
        # SPECIFIC BRANCH
        # ----------------------------------------------------

        else:

            try:

                parsed_branch_id = int(value)

            except ValueError:

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "branch_id must be "
                        "a valid integer or 'all'."
                    ),
                )

            if parsed_branch_id <= 0:

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "branch_id must be "
                        "greater than 0."
                    ),
                )

    return await service.list_rank_rules_service(
        db=db,
        current_user=current,
        branch_id=parsed_branch_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


# ============================================================
# GET SINGLE BRANCH
# ============================================================

@router.get(
    "/{branch_id}",
    response_model=RankRuleResponse,
    summary="Get Active Rank Rule for a Branch",
)
async def get_rank_rule(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one),
    client_id: Optional[int] = Query(
        None,
        description="Filter by Client ID",
    ),
):

    return await service.get_rank_rule_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
    )


# ============================================================
# UPDATE
# ============================================================

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
    client_id: Optional[int] = Query(
        None,
        description="Filter by Client ID",
    ),
):

    return await service.update_rank_rule_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
        payload=payload,
    )


# ============================================================
# DELETE
# ============================================================

@router.delete(
    "/{branch_id}",
    response_model=RankRuleResponse,
    summary="Soft Delete Active Rank Rule",
)
async def delete_rank_rule(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one),
    client_id: Optional[int] = Query(
        None,
        description="Filter by Client ID",
    ),
):

    return await service.delete_rank_rule_service(
        db=db,
        current_user=current,
        branch_id=branch_id,
    )


@router.post(
    "/redeem-current-spend/{customer_id}",
)
async def redeem_current_spend_endpoint(
    customer_id: int,
    redeem_amount: float = Query(
        ...,
        gt=0,
    ),
    db: SessionDep = None,
    current=Depends(access_one),
):
    client_id = service._extract_client_id(
        current
    )

    return await service.redeem_current_spend(
        db=db,
        customer_id=customer_id,
        client_id=client_id,
        redeem_amount=redeem_amount,
    )