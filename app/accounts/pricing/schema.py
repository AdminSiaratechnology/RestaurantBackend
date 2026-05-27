# =========================================================
# app/accounts/pricing/schema.py
# =========================================================

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator
)


# =========================================================
# BASE
# =========================================================

class PricingBase(BaseModel):

    item_id: int

    # =====================================================
    # PRICING
    # =====================================================

    price: float = Field(gt=0)

    cost_price: float = Field(
        default=0,
        ge=0
    )

    # =====================================================
    # DISCOUNT
    # =====================================================

    discount: float = Field(
        default=0,
        ge=0
    )

    # =====================================================
    # TAX
    # =====================================================

    tax: float = Field(
        default=0,
        ge=0
    )

    # =====================================================
    # EXTRA
    # =====================================================

    calories: int | None = None

    is_active: bool = True

    # =====================================================
    # TAX VALIDATION
    # =====================================================

    @field_validator("tax")
    @classmethod
    def validate_tax(cls, v):

        if v > 50:
            raise ValueError(
                "GST rate cannot exceed 50%"
            )

        return v


# =========================================================
# CREATE
# =========================================================

class PricingCreate(PricingBase):

    branch_id: int


# =========================================================
# UPDATE
# =========================================================

class PricingUpdate(BaseModel):

    price: float | None = Field(
        default=None,
        gt=0
    )

    cost_price: float | None = Field(
        default=None,
        ge=0
    )

    discount: float | None = Field(
        default=None,
        ge=0
    )

    tax: float | None = Field(
        default=None,
        ge=0
    )

    calories: int | None = None

    is_active: bool | None = None


# =========================================================
# OUTPUT
# =========================================================

class PricingOut(BaseModel):

    id: int

    client_id: int

    branch_id: int | None = None

    item_id: int

    # =====================================================
    # PRICING
    # =====================================================

    price: float

    cost_price: float | None = 0.0

    # =====================================================
    # DISCOUNT
    # =====================================================

    discount: float | None = 0.0

    # =====================================================
    # TAX
    # =====================================================

    tax: float | None = 5.0

    # =====================================================
    # EXTRA
    # =====================================================

    calories: int | None = None

    is_active: bool | None = True

    created_at: datetime

    # =====================================================
    # COMPUTED FIELDS
    # =====================================================

    @computed_field
    @property
    def cgst_rate(self) -> float:

        return round(
            (self.tax or 0.0) / 2,
            2
        )

    @computed_field
    @property
    def sgst_rate(self) -> float:

        return round(
            (self.tax or 0.0) / 2,
            2
        )

    @computed_field
    @property
    def discounted_price(self) -> float:

        base = self.price or 0.0

        disc = self.discount or 0.0

        discounted = base - (
            base * disc / 100
        )

        return round(discounted, 2)

    @computed_field
    @property
    def cgst_amount(self) -> float:

        discounted = self.discounted_price

        cgst = self.cgst_rate

        return round(
            discounted * cgst / 100,
            2
        )

    @computed_field
    @property
    def sgst_amount(self) -> float:

        discounted = self.discounted_price

        sgst = self.sgst_rate

        return round(
            discounted * sgst / 100,
            2
        )

    @computed_field
    @property
    def total_tax_amount(self) -> float:

        return round(
            self.cgst_amount +
            self.sgst_amount,
            2
        )

    @computed_field
    @property
    def total_price(self) -> float:

        return round(
            self.discounted_price +
            self.total_tax_amount,
            2
        )

    model_config = ConfigDict(
        from_attributes=True
    )