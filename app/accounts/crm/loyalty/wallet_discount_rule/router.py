from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
# from sqlalchemy.ext.asyncio import AsyncSession
from app.db.config import SessionDep

from app.accounts.crm.loyalty.wallet_discount_rule.schema import (
    WalletDiscountRuleCreate,
    WalletDiscountRuleResponse,
    WalletDiscountRuleUpdate,
    WalletPaymentCalculationResponse,
)
from app.accounts.crm.loyalty.wallet_discount_rule.service import (
    calculate_wallet_payment,
    create_wallet_discount_rule,
    delete_wallet_discount_rule,
    get_wallet_discount_rule,
    update_wallet_discount_rule,
)


router = APIRouter(
    prefix="/crm/wallet-payment-rules",
    tags=[
        "CRM - Wallet Payment Rules"
    ],
)


# =========================================================
# CREATE RULE
# =========================================================

@router.post(
    "/branch/{branch_id}",
    response_model=WalletDiscountRuleResponse,
)
async def create_wallet_rule(
    branch_id: int,
    data: WalletDiscountRuleCreate,
    db: SessionDep,
    client_id: int = Query(...),
):
    """
    Create wallet payment rule for a branch.

    Example:

    client_id = 1
    branch_id = 3

    max_wallet_discount_percent = 20

    Means customer can use maximum 20%
    of bill amount from wallet.
    """

    return await create_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
        data=data,
    )


# =========================================================
# GET RULE
# =========================================================

@router.get(
    "/branch/{branch_id}",
    response_model=WalletDiscountRuleResponse,
)
async def get_wallet_rule(
    branch_id: int,
    db: SessionDep,
    client_id: int = Query(...),
):
    """
    Get wallet payment rule for a branch.
    """

    rule = await get_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
    )

    if not rule:

        raise HTTPException(
            status_code=404,
            detail="Wallet payment rule not found.",
        )

    return rule


# =========================================================
# UPDATE RULE
# =========================================================

@router.put(
    "/branch/{branch_id}",
    response_model=WalletDiscountRuleResponse,
)
async def update_wallet_rule(
    branch_id: int,
    data: WalletDiscountRuleUpdate,
    db: SessionDep,
    client_id: int = Query(...),
):
    """
    Update wallet payment rule.
    """

    return await update_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
        data=data,
    )


# =========================================================
# DELETE / DEACTIVATE
# =========================================================

@router.delete(
    "/branch/{branch_id}",
    response_model=WalletDiscountRuleResponse,
)
async def delete_wallet_rule(
    branch_id: int,
    db: SessionDep,
    client_id: int = Query(...),
):
    """
    Deactivate wallet payment rule.

    Rule is soft-deleted by setting is_active=False.
    """

    return await delete_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
    )


# =========================================================
# CALCULATE WALLET PAYMENT
# =========================================================

@router.get(
    "/branch/{branch_id}/calculate",
    response_model=WalletPaymentCalculationResponse,
)
async def calculate_wallet_rule(
    branch_id: int,
    db: SessionDep,
    bill_amount: float = Query(
        ...,
        ge=0,
    ),
    wallet_balance: float = Query(
        ...,
        ge=0,
    ),
    client_id: int = Query(...),
):
    """
    Calculate how much wallet amount can be used
    for a particular bill.

    This endpoint DOES NOT deduct wallet balance.

    It only calculates the applicable amount.
    """

    return await calculate_wallet_payment(
        db,
        client_id=client_id,
        branch_id=branch_id,
        bill_amount=bill_amount,
        wallet_balance=wallet_balance,
    )