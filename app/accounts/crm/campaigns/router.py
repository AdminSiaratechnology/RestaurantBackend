"""
FastAPI router for CRM Campaigns.
"""

from typing import List

from fastapi import APIRouter, Query

from app.db.config import SessionDep
from app.accounts.crm.campaigns.schema import (
    CampaignCreate,
    CampaignOut,
)
from app.accounts.crm.campaigns import service

router = APIRouter(
    prefix="/crm/campaigns",
    tags=["CRM Campaigns"],
)


@router.post("", response_model=CampaignOut)
async def create_campaign(
    payload: CampaignCreate,
    db: SessionDep,
):
    return await service.create_campaign(db, payload)


@router.get("", response_model=List[CampaignOut])
async def list_campaigns(
    db: SessionDep,
    client_id: int = Query(...),
):
    return await service.get_campaigns(db, client_id)