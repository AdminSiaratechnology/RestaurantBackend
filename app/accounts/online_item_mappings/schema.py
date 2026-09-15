# app/online_item_mappings/schema.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OnlinePlatformItemMappingCreate(BaseModel):
    online_platform_connection_id: int = Field(..., gt=0)
    item_id: int = Field(..., gt=0)

    platform_item_id: str = Field(
        ...,
        min_length=1,
        max_length=150
    )

    platform_item_name: Optional[str] = Field(
        default=None,
        max_length=255
    )

    is_active: bool = True

    notes: Optional[str] = None

    @field_validator("platform_item_id")
    @classmethod
    def validate_platform_item_id(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("platform_item_id cannot be empty")

        return value

    @field_validator("platform_item_name")
    @classmethod
    def validate_platform_item_name(
        cls,
        value: Optional[str]
    ) -> Optional[str]:

        if value is None:
            return None

        value = value.strip()

        return value or None


class OnlinePlatformItemMappingUpdate(BaseModel):

    item_id: Optional[int] = Field(
        default=None,
        gt=0
    )

    platform_item_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=150
    )

    platform_item_name: Optional[str] = Field(
        default=None,
        max_length=255
    )

    is_active: Optional[bool] = None

    notes: Optional[str] = None

    @field_validator("platform_item_id")
    @classmethod
    def validate_platform_item_id(
        cls,
        value: Optional[str]
    ) -> Optional[str]:

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("platform_item_id cannot be empty")

        return value

    @field_validator("platform_item_name")
    @classmethod
    def validate_platform_item_name(
        cls,
        value: Optional[str]
    ) -> Optional[str]:

        if value is None:
            return None

        value = value.strip()

        return value or None


class OnlinePlatformItemMappingOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int

    online_platform_connection_id: int

    item_id: int

    platform_item_id: str

    platform_item_name: Optional[str]

    is_active: bool

    notes: Optional[str]

    created_at: datetime

    updated_at: datetime


class OnlinePlatformItemMappingListResponse(BaseModel):

    items: list[OnlinePlatformItemMappingOut]

    total: int