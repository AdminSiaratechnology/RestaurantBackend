from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession
from app.db.config import SessionDep

from app.accounts.crm.loyalty.wallet_discount_rule.model import (
    WalletDiscountRule,
)

from app.accounts.crm.loyalty.wallet_discount_rule.schema import (
    WalletDiscountRuleCreate,
    WalletDiscountRuleUpdate,
)


# =========================================================
# GET RULE
# =========================================================

async def get_wallet_discount_rule(
    db: SessionDep,
    *,
    client_id: int,
    branch_id: int,
    active_only: bool = False,
) -> Optional[WalletDiscountRule]:

    query = select(
        WalletDiscountRule
    ).where(
        WalletDiscountRule.client_id == client_id,
        WalletDiscountRule.branch_id == branch_id,
    )

    if active_only:
        query = query.where(
            WalletDiscountRule.is_active.is_(True)
        )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# CREATE RULE
# =========================================================

async def create_wallet_discount_rule(
    db: SessionDep,
    *,
    client_id: int,
    branch_id: int,
    data: WalletDiscountRuleCreate,
) -> WalletDiscountRule:

    # -----------------------------------------------------
    # CHECK EXISTING RULE
    # -----------------------------------------------------

    existing_rule = await get_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
    )

    if existing_rule:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Wallet payment rule already exists "
                "for this branch."
            ),
        )

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    rule = WalletDiscountRule(
        client_id=client_id,
        branch_id=branch_id,
        max_wallet_discount_percent=(
            data.max_wallet_discount_percent
        ),
        is_active=data.is_active,
    )

    db.add(rule)

    await db.commit()

    await db.refresh(rule)

    return rule


# =========================================================
# UPDATE RULE
# =========================================================

async def update_wallet_discount_rule(
    db: SessionDep,
    *,
    client_id: int,
    branch_id: int,
    data: WalletDiscountRuleUpdate,
) -> WalletDiscountRule:

    rule = await get_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
    )

    if not rule:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet payment rule not found.",
        )

    # -----------------------------------------------------
    # UPDATE PERCENTAGE
    # -----------------------------------------------------

    if data.max_wallet_discount_percent is not None:

        rule.max_wallet_discount_percent = (
            data.max_wallet_discount_percent
        )

    # -----------------------------------------------------
    # UPDATE STATUS
    # -----------------------------------------------------

    if data.is_active is not None:

        rule.is_active = data.is_active

    await db.commit()

    await db.refresh(rule)

    return rule


# =========================================================
# DELETE / DEACTIVATE
# =========================================================

async def delete_wallet_discount_rule(
    db: SessionDep,
    *,
    client_id: int,
    branch_id: int,
) -> WalletDiscountRule:

    rule = await get_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
    )

    if not rule:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet payment rule not found.",
        )

    # -----------------------------------------------------
    # SOFT DELETE
    # -----------------------------------------------------

    rule.is_active = False

    await db.commit()

    await db.refresh(rule)

    return rule


# =========================================================
# CALCULATE WALLET PAYMENT
# =========================================================

async def calculate_wallet_payment(
    db: SessionDep,
    *,
    client_id: int,
    branch_id: int,
    bill_amount: float,
    wallet_balance: float,
) -> dict:

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if bill_amount < 0:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bill amount cannot be negative.",
        )

    if wallet_balance < 0:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet balance cannot be negative.",
        )

    # -----------------------------------------------------
    # GET ACTIVE RULE
    # -----------------------------------------------------

    rule = await get_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
        active_only=True,
    )

    # -----------------------------------------------------
    # NO ACTIVE RULE
    # -----------------------------------------------------

    if not rule:

        return {
            "bill_amount": round(
                bill_amount,
                2,
            ),
            "wallet_balance": round(
                wallet_balance,
                2,
            ),
            "discount_percent": 0.0,
            "maximum_wallet_amount": 0.0,
            "applicable_wallet_amount": 0.0,
            "customer_payable_amount": round(
                bill_amount,
                2,
            ),
        }

    # -----------------------------------------------------
    # MAXIMUM WALLET AMOUNT
    # -----------------------------------------------------

    maximum_wallet_amount = (
        bill_amount
        * rule.max_wallet_discount_percent
        / 100
    )

    # -----------------------------------------------------
    # ACTUAL WALLET AMOUNT
    #
    # Cannot exceed:
    #
    # 1. Wallet balance
    # 2. Rule percentage amount
    # 3. Bill amount
    # -----------------------------------------------------

    applicable_wallet_amount = min(
        wallet_balance,
        maximum_wallet_amount,
        bill_amount,
    )

    # -----------------------------------------------------
    # CUSTOMER PAYABLE
    # -----------------------------------------------------

    customer_payable_amount = (
        bill_amount
        - applicable_wallet_amount
    )

    return {
        "bill_amount": round(
            bill_amount,
            2,
        ),
        "wallet_balance": round(
            wallet_balance,
            2,
        ),
        "discount_percent": round(
            rule.max_wallet_discount_percent,
            2,
        ),
        "maximum_wallet_amount": round(
            maximum_wallet_amount,
            2,
        ),
        "applicable_wallet_amount": round(
            applicable_wallet_amount,
            2,
        ),
        "customer_payable_amount": round(
            customer_payable_amount,
            2,
        ),
    }