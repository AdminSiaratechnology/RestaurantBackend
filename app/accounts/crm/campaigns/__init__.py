"""
CRM Campaigns Module.
"""

from app.accounts.crm.campaigns.model import (
    Campaign,
    CampaignLog,
    CustomerCoupon,
)
from app.accounts.crm.campaigns.router import router

__all__ = [
    "Campaign",
    "CampaignLog",
    "CustomerCoupon",
    "router",
]