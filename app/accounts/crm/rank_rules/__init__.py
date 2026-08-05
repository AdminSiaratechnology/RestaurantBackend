"""
CRM Branch Rank Rules Package.
"""

from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.crm.rank_rules.repository import RankRuleRepository
from app.accounts.crm.rank_rules.router import router

__all__ = [
    "CRMBranchRankRule",
    "RankRuleRepository",
    "router",
]
