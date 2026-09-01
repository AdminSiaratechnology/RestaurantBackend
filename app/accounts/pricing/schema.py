# =========================================================
# app/accounts/pricing/schema.py
# =========================================================

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


# =========================================================
# BASE
# =========================================================

class PricingBase(BaseModel):

    item_id: int

    price: float = Field(
        gt=0,
    )

    cost_price: float = Field(
        default=0,
        ge=0,
    )

    discount: float = Field(
        default=0,
        ge=0,
    )

    tax: float = Field(
        default=0,
        ge=0,
    )

    calories: int | None = None

    is_active: bool = True

    @field_validator("tax")
    @classmethod
    def validate_tax(
        cls,
        value: float,
    ) -> float:

        if value > 100:

            raise ValueError(
                "Tax rate cannot exceed 100%"
            )

        return value


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
        gt=0,
    )

    cost_price: float | None = Field(
        default=None,
        ge=0,
    )

    discount: float | None = Field(
        default=None,
        ge=0,
    )

    tax: float | None = Field(
        default=None,
        ge=0,
    )

    calories: int | None = None

    is_active: bool | None = None

    @field_validator("tax")
    @classmethod
    def validate_tax(
        cls,
        value: float | None,
    ) -> float | None:

        if value is None:
            return None

        if value > 100:

            raise ValueError(
                "Tax rate cannot exceed 100%"
            )

        return value


# =========================================================
# OUTPUT
# =========================================================

class PricingOut(BaseModel):

    id: int

    client_id: int

    branch_id: int

    item_id: int

    # =====================================================
    # PRICE
    # =====================================================

    price: float

    cost_price: float | None = 0.0

    discount: float | None = 0.0

    # =====================================================
    # TAX
    # =====================================================

    tax: float = 0.0

    tax_type: str

    cgst_rate: float = 0.0

    sgst_rate: float = 0.0

    # =====================================================
    # EXTRA
    # =====================================================

    calories: int | None = None

    is_active: bool | None = True

    created_at: datetime

    # =====================================================
    # CALCULATIONS
    # =====================================================

    @computed_field
    @property
    def discounted_price(self) -> float:

        base = self.price or 0.0

        discount = self.discount or 0.0

        discounted = base - (
            base * discount / 100
        )

        return round(
            discounted,
            2,
        )

    # =====================================================
    # GST AMOUNT
    # =====================================================

    @computed_field
    @property
    def cgst_amount(self) -> float:

        if self.tax_type != "GST":

            return 0.0

        return round(
            self.discounted_price
            * self.cgst_rate
            / 100,
            2,
        )

    @computed_field
    @property
    def sgst_amount(self) -> float:

        if self.tax_type != "GST":

            return 0.0

        return round(
            self.discounted_price
            * self.sgst_rate
            / 100,
            2,
        )

    # =====================================================
    # VAT AMOUNT
    # =====================================================

    @computed_field
    @property
    def vat_amount(self) -> float:

        if self.tax_type != "VAT":

            return 0.0

        return round(
            self.discounted_price
            * self.tax
            / 100,
            2,
        )

    # =====================================================
    # TOTAL TAX
    # =====================================================

    @computed_field
    @property
    def total_tax_amount(self) -> float:

        if self.tax_type == "GST":

            return round(
                self.cgst_amount
                + self.sgst_amount,
                2,
            )

        return round(
            self.vat_amount,
            2,
        )

    # =====================================================
    # TOTAL PRICE
    # =====================================================

    @computed_field
    @property
    def total_price(self) -> float:

        return round(
            self.discounted_price
            + self.total_tax_amount,
            2,
        )

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# TAX HISTORY
# =========================================================

class TaxHistoryOut(BaseModel):

    id: int

    old_tax: float

    new_tax: float

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )