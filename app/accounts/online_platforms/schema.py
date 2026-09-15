# app/online_platforms/schema.py

from datetime import datetime
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# =========================================================
# CREATE
# =========================================================

class OnlinePlatformConnectionCreate(BaseModel):

    branch_id: int = Field(
        ...,
        gt=0,
    )

    platform: str = Field(
        ...,
        min_length=2,
        max_length=50,
    )

    display_name: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    connection_status: str = Field(
        default="pending",
        max_length=30,
    )

    is_active: bool = True

    api_key: Optional[str] = None

    api_secret: Optional[str] = None

    access_token: Optional[str] = None

    refresh_token: Optional[str] = None

    webhook_secret: Optional[str] = None

    platform_restaurant_id: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    platform_store_id: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    config: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        value = value.strip().lower()

        if not value:
            raise ValueError("Platform is required")

        return value

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(cls, value: str) -> str:
        value = value.strip().lower()

        allowed = {
            "pending",
            "connected",
            "disconnected",
            "error",
        }

        if value not in allowed:
            raise ValueError(
                f"connection_status must be one of: "
                f"{', '.join(sorted(allowed))}"
            )

        return value


# =========================================================
# UPDATE
# =========================================================

class OnlinePlatformConnectionUpdate(BaseModel):

    platform: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=50,
    )

    display_name: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    connection_status: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    is_active: Optional[bool] = None

    api_key: Optional[str] = None

    api_secret: Optional[str] = None

    access_token: Optional[str] = None

    refresh_token: Optional[str] = None

    webhook_secret: Optional[str] = None

    platform_restaurant_id: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    platform_store_id: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    config: Optional[dict[str, Any]] = None

    last_error: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: Optional[str]) -> Optional[str]:

        if value is None:
            return value

        value = value.strip().lower()

        if not value:
            raise ValueError("Platform cannot be empty")

        return value

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(
        cls,
        value: Optional[str],
    ) -> Optional[str]:

        if value is None:
            return value

        value = value.strip().lower()

        allowed = {
            "pending",
            "connected",
            "disconnected",
            "error",
        }

        if value not in allowed:
            raise ValueError(
                f"connection_status must be one of: "
                f"{', '.join(sorted(allowed))}"
            )

        return value


# =========================================================
# RESPONSE
# =========================================================

class OnlinePlatformConnectionOut(BaseModel):

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    branch_id: int

    platform: str

    display_name: Optional[str]

    connection_status: str

    is_active: bool

    platform_restaurant_id: Optional[str]

    platform_store_id: Optional[str]

    config: dict[str, Any]

    last_error: Optional[str]

    last_connected_at: Optional[datetime]

    created_at: datetime

    updated_at: datetime


# =========================================================
# LIST RESPONSE
# =========================================================

class OnlinePlatformConnectionListResponse(BaseModel):

    items: list[OnlinePlatformConnectionOut]

    total: int