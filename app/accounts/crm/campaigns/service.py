"""
Campaign Services.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.campaigns.model import Campaign
from app.accounts.crm.campaigns.schema import CampaignCreate


async def create_campaign(
    db: AsyncSession,
    payload: CampaignCreate,
) -> Campaign:

    campaign = Campaign(**payload.model_dump())

    db.add(campaign)

    await db.flush()

    return campaign


async def get_campaigns(
    db: AsyncSession,
    client_id: int,
) -> List[Campaign]:

    stmt = (
        select(Campaign)
        .where(Campaign.client_id == client_id)
    )

    result = await db.execute(stmt)

    return result.scalars().all()