"""
Services for Customer Loyalty Accounts & Transactions.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.customer.model import Customer
from app.accounts.crm.loyalty.model import (
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
)


async def get_loyalty_account(
    db: AsyncSession,
    customer_id: int,
) -> Optional[CustomerLoyaltyAccount]:

    # Check if loyalty account already exists
    stmt = select(CustomerLoyaltyAccount).where(
        CustomerLoyaltyAccount.customer_id == customer_id
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account:
        return account

    # Check customer exists
    customer_stmt = select(Customer).where(Customer.id == customer_id)
    customer_result = await db.execute(customer_stmt)
    customer = customer_result.scalar_one_or_none()

    if customer is None:
        return None

    # Auto create loyalty account
    account = CustomerLoyaltyAccount(
        customer_id=customer.id,
        client_id=customer.client_id,
        total_points_earned=0.0,
        total_points_redeemed=0.0,
        current_points_balance=0.0,
    )

    db.add(account)
    await db.commit()
    await db.refresh(account)

    return account


async def get_loyalty_transactions(
    db: AsyncSession,
    customer_id: int,
) -> List[LoyaltyTransaction]:

    stmt = (
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.customer_id == customer_id)
        .order_by(LoyaltyTransaction.created_at.desc())
    )

    result = await db.execute(stmt)
    return result.scalars().all()