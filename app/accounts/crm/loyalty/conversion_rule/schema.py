"""
app/accounts/crm/loyalty/conversion_rule/schema.py

Pydantic schemas for loyalty conversion rules.
"""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class LoyaltyConversionRuleCreate(BaseModel):

    points_required: float = Field(
        ...,
        gt=0,
        description="Number of loyalty points required",
    )

    rupee_value: float = Field(
        ...,
        gt=0,
        description="Rupee value received",
    )

    is_active: bool = True


class LoyaltyConversionRuleUpdate(BaseModel):

    points_required: float | None = Field(
        default=None,
        gt=0,
    )

    rupee_value: float | None = Field(
        default=None,
        gt=0,
    )

    is_active: bool | None = None


class LoyaltyConversionRuleOut(BaseModel):

    id: int = 0

    client_id: int = 1

    branch_id: int

    points_required: float = 10.0

    rupee_value: float = 5.0

    is_active: bool = True

    created_at: datetime | None = None

    updated_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )