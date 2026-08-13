"""
app/accounts/crm/loyalty/conversion_rule/router.py

FastAPI router for branch-wise loyalty conversion rules.
"""

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.db.config import SessionDep

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
):

    rule = await service.get_rule(
        db,
        branch_id=branch_id,
    )

    if rule is None:
        return LoyaltyConversionRuleOut(
            id=0,
            client_id=1,
            branch_id=branch_id,
            points_required=10.0,
            rupee_value=5.0,
            is_active=True,
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
    client_id: int,
    payload: LoyaltyConversionRuleCreate,
    db: SessionDep,
):

    return await service.create_rule(
        db,
        client_id=client_id,
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
):

    rule = await service.update_rule(
        db,
        branch_id=branch_id,
        points_required=payload.points_required,
        rupee_value=payload.rupee_value,
        is_active=payload.is_active,
    )

    if rule is None:

        raise HTTPException(
            status_code=404,
            detail="Loyalty conversion rule not found",
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
):

    rule = await service.deactivate_rule(
        db,
        branch_id=branch_id,
    )

    if rule is None:

        raise HTTPException(
            status_code=404,
            detail="Loyalty conversion rule not found",
        )

    return {
        "message": (
            "Loyalty conversion rule "
            "deactivated successfully"
        )
    }