"""
CRM Handlers package.
"""

from app.accounts.crm.handlers.base import BaseCRMHandler, CRMContext
from app.accounts.crm.handlers.customer_history import CustomerHistoryHandler
from app.accounts.crm.handlers.customer_stats import CustomerStatsHandler
from app.accounts.crm.handlers.rank import RankHandler
from app.accounts.crm.handlers.loyalty import LoyaltyHandler
from app.accounts.crm.handlers.wallet import WalletHandler
from app.accounts.crm.handlers.coupon import CouponHandler
from app.accounts.crm.handlers.campaign import CampaignHandler
from app.accounts.crm.handlers.notification import NotificationHandler

__all__ = [
    "BaseCRMHandler",
    "CRMContext",
    "CustomerHistoryHandler",
    "CustomerStatsHandler",
    "RankHandler",
    "LoyaltyHandler",
    "WalletHandler",
    "CouponHandler",
    "CampaignHandler",
    "NotificationHandler",
]
