"""
app/accounts/crm/loyalty/conversion_rule/router.py

FastAPI router for branch-wise loyalty conversion rules.
"""

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.db.config import SessionDep
from app.accounts.branch.model import Branch
from app.accounts.crm.loyalty.conversion_rule import service

from app.accounts.crm.loyalty.conversion_rule.schema import (
    LoyaltyConversionRuleCreate,
    LoyaltyConversionRuleOut,
    LoyaltyConversionRuleUpdate,
)


router = APIRouter(
    prefix="/crm/loyalty/conversion-rules",
    tags=["CRM Loyalty Conversion Rules"],
)


# ============================================================
# GET RULE
# ============================================================


@router.get(
    "/branch/{branch_id}",
    response_model=LoyaltyConversionRuleOut,
)
async def get_conversion_rule(
    branch_id: int,
    db: SessionDep,
    client_id: int | None = Query(None),
):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    target_client_id = client_id or branch.client_id

    rule = await service.get_rule(
        db,
        client_id=target_client_id,
        branch_id=branch_id,
    )

    if rule is None:
        rule = await service.get_or_create_loyalty_conversion_rule(
            db,
            client_id=target_client_id,
            branch_id=branch_id,
        )

    return rule


# ============================================================
# CREATE RULE
# ============================================================


@router.post(
    "/branch/{branch_id}",
    response_model=LoyaltyConversionRuleOut,
)
async def create_conversion_rule(
    branch_id: int,
    payload: LoyaltyConversionRuleCreate,
    db: SessionDep,
    client_id: int | None = Query(None),
):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    target_client_id = client_id or branch.client_id

    return await service.create_rule(
        db,
        client_id=target_client_id,
        branch_id=branch_id,
        points_required=payload.points_required,
        rupee_value=payload.rupee_value,
        is_active=payload.is_active,
    )


# ============================================================
# UPDATE RULE
# ============================================================


@router.put(
    "/branch/{branch_id}",
    response_model=LoyaltyConversionRuleOut,
)
async def update_conversion_rule(
    branch_id: int,
    payload: LoyaltyConversionRuleUpdate,
    db: SessionDep,
    client_id: int | None = Query(None),
):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    target_client_id = client_id or branch.client_id

    rule = await service.update_rule(
        db,
        client_id=target_client_id,
        branch_id=branch_id,
        points_required=payload.points_required,
        rupee_value=payload.rupee_value,
        is_active=payload.is_active,
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail="No active loyalty conversion rule is configured for this branch.",
        )

    return rule


# ============================================================
# DELETE / DEACTIVATE
# ============================================================


@router.delete(
    "/branch/{branch_id}",
)
async def delete_conversion_rule(
    branch_id: int,
    db: SessionDep,
    client_id: int | None = Query(None),
):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    target_client_id = client_id or branch.client_id

    rule = await service.deactivate_rule(
        db,
        client_id=target_client_id,
        branch_id=branch_id,
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail="No active loyalty conversion rule is configured for this branch.",
        )

    return {
        "message": (
            "Loyalty conversion rule "
            "deactivated successfully"
        )
    }