from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.customer.model import Customer
from app.accounts.crm.wallet.model import (
    CustomerWalletAccount,
    WalletTransaction,
)


async def get_wallet_account(
    db: AsyncSession,
    customer_id: int,
) -> Optional[CustomerWalletAccount]:

    stmt = select(CustomerWalletAccount).where(
        CustomerWalletAccount.customer_id == customer_id
    )

    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account:
        return account

    # Customer exists?
    customer_result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )

    customer = customer_result.scalar_one_or_none()

    if customer is None:
        return None

    # Auto create wallet account
    account = CustomerWalletAccount(
        customer_id=customer.id,
        client_id=customer.client_id,
        balance=0.0,
        total_recharged=0.0,
        total_spent=0.0,
    )

    db.add(account)
    await db.commit()
    await db.refresh(account)

    return account


async def get_wallet_transactions(
    db: AsyncSession,
    customer_id: int,
) -> List[WalletTransaction]:

    stmt = (
        select(WalletTransaction)
        .where(WalletTransaction.customer_id == customer_id)
        .order_by(WalletTransaction.created_at.desc())
    )

    result = await db.execute(stmt)
    return result.scalars().all()