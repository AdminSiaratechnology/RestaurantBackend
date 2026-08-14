from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.crm.wallet.model import WalletTransaction
from app.accounts.crm.loyalty.wallet_discount_rule.model import (
    WalletDiscountRule,
)
from app.accounts.customer.model import Customer


async def get_customer_wallet(
    db,
    customer_id: int,
):
    result = await db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .with_for_update()
    )

    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="CRM customer not found",
        )

    return customer


async def get_wallet_discount_rule(
    db,
    client_id: int,
    branch_id: int,
):
    result = await db.execute(
        select(WalletDiscountRule)
        .where(
            WalletDiscountRule.client_id == client_id,
            WalletDiscountRule.branch_id == branch_id,
            WalletDiscountRule.is_active.is_(True),
        )
    )

    return result.scalar_one_or_none()


async def calculate_wallet_discount(
    db,
    customer_id: int,
    client_id: int,
    branch_id: int,
    amount: float,
):
    """
    Calculates the maximum wallet amount that can be used.

    Wallet discount is calculated AFTER offer discount.

    Example:
        amount = ₹900
        rule = 20%
        wallet = ₹500

        max allowed = ₹180
        wallet discount = ₹180
    """

    if amount <= 0:
        return {
            "wallet_balance": 0.0,
            "wallet_percent": 0.0,
            "max_wallet_discount": 0.0,
            "wallet_discount": 0.0,
        }

    customer = await get_customer_wallet(
        db,
        customer_id,
    )

    wallet_balance = round(
        max(customer.wallet_balance, 0.0),
        2,
    )

    rule = await get_wallet_discount_rule(
        db,
        client_id,
        branch_id,
    )

    if not rule:
        return {
            "wallet_balance": wallet_balance,
            "wallet_percent": 0.0,
            "max_wallet_discount": 0.0,
            "wallet_discount": 0.0,
        }

    wallet_percent = float(
        rule.max_wallet_discount_percent
    )

    max_wallet_discount = round(
        amount * wallet_percent / 100,
        2,
    )

    wallet_discount = round(
        min(
            wallet_balance,
            max_wallet_discount,
            amount,
        ),
        2,
    )

    return {
        "wallet_balance": wallet_balance,
        "wallet_percent": wallet_percent,
        "max_wallet_discount": max_wallet_discount,
        "wallet_discount": wallet_discount,
    }


async def debit_wallet(
    db,
    customer_id: int,
    client_id: int,
    branch_id: int,
    amount: float,
    reference_type: str,
    reference_id: int,
    notes: str | None = None,
):
    """
    Atomically deduct wallet balance.

    Customer must already be locked using SELECT FOR UPDATE.
    """

    if amount <= 0:
        return None

    customer = await get_customer_wallet(
        db,
        customer_id,
    )

    current_balance = round(
        max(customer.wallet_balance, 0.0),
        2,
    )

    if current_balance < amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient wallet balance",
        )

    new_balance = round(
        current_balance - amount,
        2,
    )

    customer.wallet_balance = new_balance

    transaction = WalletTransaction(
        customer_id=customer_id,
        client_id=client_id,
        branch_id=branch_id,
        transaction_type="DEBIT",
        amount=amount,
        balance_before=current_balance,
        balance_after=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )

    db.add(transaction)

    return transaction