"""
app/accounts/crm/rank_rules/schema.py

Pydantic v2 schemas for Branch-wise Customer Rank Rule Management.
Enforces strict range validation to prevent gaps and overlapping thresholds.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RankRuleBase(BaseModel):
    bronze_min: float = Field(default=0.0, ge=0, description="Minimum spend for Bronze (must be 0)")
    bronze_max: float = Field(..., gt=0, description="Maximum spend for Bronze")
    silver_min: float = Field(..., gt=0, description="Minimum spend for Silver")
    silver_max: float = Field(..., gt=0, description="Maximum spend for Silver")
    gold_min: float = Field(..., gt=0, description="Minimum spend for Gold")

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.bronze_min != 0.0:
            raise ValueError("bronze_min must be 0")

        if self.bronze_max <= self.bronze_min:
            raise ValueError(
                f"bronze_max ({self.bronze_max}) must be greater than bronze_min ({self.bronze_min})"
            )

        if self.silver_min != self.bronze_max:
            raise ValueError(
                f"silver_min ({self.silver_min}) must equal bronze_max ({self.bronze_max}). "
                "Gaps and overlapping ranges between Bronze and Silver are not allowed."
            )

        if self.silver_max <= self.silver_min:
            raise ValueError(
                f"silver_max ({self.silver_max}) must be greater than silver_min ({self.silver_min})"
            )

        if self.gold_min != self.silver_max:
            raise ValueError(
                f"gold_min ({self.gold_min}) must equal silver_max ({self.silver_max}). "
                "Gaps and overlapping ranges between Silver and Gold are not allowed."
            )

        if self.gold_min <= 0.0:
            raise ValueError(f"gold_min ({self.gold_min}) must be greater than 0")

        return self


class RankRuleCreate(RankRuleBase):
    branch_id: int = Field(..., gt=0)
    client_id: Optional[int] = Field(default=None)


class RankRuleUpdate(BaseModel):
    bronze_min: Optional[float] = Field(default=None, ge=0)
    bronze_max: Optional[float] = Field(default=None, gt=0)
    silver_min: Optional[float] = Field(default=None, gt=0)
    silver_max: Optional[float] = Field(default=None, gt=0)
    gold_min: Optional[float] = Field(default=None, gt=0)
    is_active: Optional[bool] = Field(default=None)

    model_config = ConfigDict(extra="forbid")


class RankRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: Optional[int] = None
    branch_id: int

    bronze_min: float = 0.0
    bronze_max: float
    silver_min: float
    silver_max: float
    gold_min: float

    is_active: bool

    created_at: datetime
    updated_at: datetime


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class RankRuleListResponse(BaseModel):
    items: List[RankRuleResponse]
    pagination: PaginationResponse