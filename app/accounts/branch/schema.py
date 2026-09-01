from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.accounts.branch.model import statusEnum


# ============================================================
# CREATE BRANCH
# ============================================================

class BranchCreate(BaseModel):

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    address: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    city: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    country: str = Field(
        default="India",
        min_length=1,
        max_length=100,
    )

    state: str = Field(
        default="Delhi",
        min_length=1,
        max_length=100,
    )

    pincode: str = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
    )

    decimal_places: int = Field(
        default=2,
        ge=0,
        le=6,
    )

    status: statusEnum = statusEnum.ACTIVE

    client_id: int

    brand_id: int | None = None

    # ========================================================
    # VALIDATORS
    # ========================================================

    @field_validator("currency")
    @classmethod
    def validate_currency(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()

    @field_validator(
        "country",
        "state",
        "city",
        "name",
        "address",
    )
    @classmethod
    def validate_text_fields(
        cls,
        value: str,
    ) -> str:
        return value.strip()

    @field_validator("pincode")
    @classmethod
    def validate_pincode(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Pincode cannot be empty"
            )

        return value


# ============================================================
# BRANCH RESPONSE
# ============================================================

class BranchOut(BaseModel):

    id: int

    name: str

    client_id: int

    branch_code: str

    brand_id: int | None = None

    address: str

    city: str

    country: str

    state: str

    pincode: str

    # ========================================================
    # CURRENCY
    # ========================================================

    currency: str

    decimal_places: int

    # ========================================================
    # TAX TYPE
    #
    # GST for India
    # VAT for other countries
    # ========================================================

    tax_type: str

    status: statusEnum

    created_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# UPDATE BRANCH
# ============================================================

class BranchUpdate(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    address: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    city: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    country: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    pincode: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    decimal_places: int | None = Field(
        default=None,
        ge=0,
        le=6,
    )

    brand_id: int | None = None

    status: statusEnum | None = None

    # ========================================================
    # VALIDATORS
    # ========================================================

    @field_validator("currency")
    @classmethod
    def validate_currency(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        return value.strip().upper()

    @field_validator(
        "country",
        "state",
        "city",
        "name",
        "address",
        "pincode",
    )
    @classmethod
    def validate_text_fields(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        return value.strip()


# ============================================================
# CHANGE STATUS
# ============================================================

class BranchStatusUpdate(BaseModel):

    status: statusEnum