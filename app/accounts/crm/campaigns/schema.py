"""
Pydantic schemas for CRM Campaigns.
"""

from datetime import datetime

from pydantic import BaseModel


class CampaignBase(BaseModel):
    name: str
    campaign_type: str
    message_template: str
    channel: str = "WHATSAPP"
    is_active: bool = True


class CampaignCreate(CampaignBase):
    client_id: int


class CampaignOut(CampaignBase):
    id: int
    client_id: int
    created_at: datetime

    class Config:
        from_attributes = True