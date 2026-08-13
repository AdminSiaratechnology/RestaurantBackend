"""
app/accounts/crm/rank_rules/schema.py
"""

from datetime import datetime
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RankRuleBase(BaseModel):

    bronze_min: float = Field(
        default=0.0,
        ge=0,
    )

    bronze_max: float = Field(
        ...,
        gt=0,
    )

    silver_min: float = Field(
        ...,
        gt=0,
    )

    silver_max: float = Field(
        ...,
        gt=0,
    )

    gold_min: float = Field(
        ...,
        gt=0,
    )

    bronze_pts: float = Field(
        default=1.0,
        ge=0,
    )

    silver_pts: float = Field(
        default=2.0,
        ge=0,
    )

    gold_pts: float = Field(
        default=3.0,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_ranges(self):

        if self.bronze_min != 0:
            raise ValueError(
                "bronze_min must be 0."
            )

        if self.bronze_max <= self.bronze_min:
            raise ValueError(
                "bronze_max must be greater than bronze_min."
            )

        if self.silver_min != self.bronze_max:
            raise ValueError(
                "silver_min must equal bronze_max."
            )

        if self.silver_max <= self.silver_min:
            raise ValueError(
                "silver_max must be greater than silver_min."
            )

        if self.gold_min != self.silver_max:
            raise ValueError(
                "gold_min must equal silver_max."
            )

        return self


class RankRuleCreate(RankRuleBase):

    branch_id: int = Field(
        ...,
        gt=0,
    )

    client_id: Optional[int] = Field(
        default=None,
    )


class RankRuleUpdate(BaseModel):

    branch_id: Optional[int] = Field(
        default=None,
        gt=0,
    )

    bronze_min: Optional[float] = Field(
        default=None,
        ge=0,
    )

    bronze_max: Optional[float] = Field(
        default=None,
        gt=0,
    )

    silver_min: Optional[float] = Field(
        default=None,
        gt=0,
    )

    silver_max: Optional[float] = Field(
        default=None,
        gt=0,
    )

    gold_min: Optional[float] = Field(
        default=None,
        gt=0,
    )

    bronze_pts: Optional[float] = Field(
        default=None,
        ge=0,
    )

    silver_pts: Optional[float] = Field(
        default=None,
        ge=0,
    )

    gold_pts: Optional[float] = Field(
        default=None,
        ge=0,
    )

    is_active: Optional[bool] = None

    model_config = ConfigDict(
        extra="ignore",
    )


class RankRuleResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int = 0

    client_id: int = 1

    branch_id: int

    bronze_min: float = 0.0
    bronze_max: float = 15000.0

    silver_min: float = 15000.0
    silver_max: float = 35000.0

    gold_min: float = 35000.0

    bronze_pts: float = 1.0
    silver_pts: float = 2.0
    gold_pts: float = 3.0

    is_active: bool = True

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginationResponse(BaseModel):

    page: int
    page_size: int
    total: int
    total_pages: int


class RankRuleListResponse(BaseModel):

    items: List[RankRuleResponse]

    pagination: PaginationResponse