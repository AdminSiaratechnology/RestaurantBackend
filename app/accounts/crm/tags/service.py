"""
app/accounts/crm/tags/service.py

Services for Customer Tags.
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.accounts.crm.tags.model import CustomerTag
from app.accounts.crm.tags.schema import CustomerTagCreate


async def create_tag(db: AsyncSession, payload: CustomerTagCreate) -> CustomerTag:
    tag = CustomerTag(**payload.model_dump())
    db.add(tag)
    await db.flush()
    return tag


async def get_customer_tags(db: AsyncSession, customer_id: int) -> List[CustomerTag]:
    stmt = select(CustomerTag).where(CustomerTag.customer_id == customer_id)
    res = await db.execute(stmt)
    return res.scalars().all()
