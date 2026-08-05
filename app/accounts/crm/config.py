"""
app/accounts/crm/config.py

Configuration and business rule constants for the CRM Background Processing Module.
Includes configurable rank thresholds, loyalty conversion rates, retry policies, and Redis stream keys.
"""

import os
from pydantic import BaseModel, Field


class RankThresholds(BaseModel):
    """Business rules for customer rank classification based on total spend or visit count."""
    SILVER_MIN_SPEND: float = Field(default=5000.0, description="Minimum spend for Silver rank")
    GOLD_MIN_SPEND: float = Field(default=20000.0, description="Minimum spend for Gold rank")
    SILVER_MIN_VISITS: int = Field(default=5, description="Minimum visits for Silver rank")
    GOLD_MIN_VISITS: int = Field(default=20, description="Minimum visits for Gold rank")


class LoyaltyConfig(BaseModel):
    """Business rules for loyalty point calculation."""
    POINTS_PER_AMOUNT: float = Field(default=100.0, description="Amount in currency (e.g. ₹100) per point unit")
    POINTS_EARNED_PER_UNIT: float = Field(default=1.0, description="Points earned per unit spent (e.g. 1 point per ₹100)")
    POINT_MONETARY_VALUE: float = Field(default=1.0, description="Monetary value of 1 point during redemption (e.g. ₹1)")


class RetryConfig(BaseModel):
    """Retry and Dead Letter Queue policies."""
    MAX_RETRIES: int = Field(default=3, description="Maximum retry attempts before DLQ")
    INITIAL_BACKOFF_SECONDS: float = Field(default=1.0, description="Base backoff delay in seconds")
    BACKOFF_MULTIPLIER: float = Field(default=2.0, description="Exponential backoff factor")


class CRMConfig(BaseModel):
    """Master CRM Configuration settings."""
    REDIS_STREAM_KEY: str = Field(default="crm:events:bill_completed", description="Redis stream for CRM events")
    REDIS_CONSUMER_GROUP: str = Field(default="crm_workers_group", description="Redis consumer group name")
    REDIS_CONSUMER_NAME: str = Field(default_factory=lambda: f"crm_worker_{os.getpid()}", description="Unique consumer instance name")
    REDIS_DLQ_KEY: str = Field(default="crm:events:dlq", description="Dead Letter Queue key for failed events")
    
    # IDEMPOTENCY
    IDEMPOTENCY_TTL_SECONDS: int = Field(default=604800, description="Redis idempotency key TTL (7 days)")

    # BUSINESS RULES
    ranks: RankThresholds = Field(default_factory=RankThresholds)
    loyalty: LoyaltyConfig = Field(default_factory=LoyaltyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)


# Global CRM config instance
crm_config = CRMConfig()
