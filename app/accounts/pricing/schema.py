from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


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
        le=100,
    )

    # TOTAL TAX RATE
    #
    # GST:
    #   tax=18 -> CGST=9 + SGST=9
    #
    # VAT:
    #   tax=15 -> VAT=15

    tax: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    calories: int | None = None

    is_active: bool = True


class PricingCreate(
    PricingBase
):
    branch_id: int


class PricingUpdate(
    BaseModel
):

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
        le=100,
    )

    tax: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    calories: int | None = None

    is_active: bool | None = None


class PricingOut(
    BaseModel
):

    id: int

    client_id: int

    branch_id: int

    item_id: int

    price: float

    cost_price: float = 0.0

    discount: float = 0.0

    tax: float = 0.0

    tax_type: str = "GST"

    @field_validator(
        "tax_type",
        mode="before",
    )
    @classmethod
    def validate_tax_type(
        cls,
        value,
    ):
        if value is None:
            return "GST"

        value = str(value).strip().upper()

        if value not in {
            "GST",
            "VAT",
        }:
            return "GST"

        return value

    cgst_rate: float = 0.0

    sgst_rate: float = 0.0

    calories: int | None = None

    is_active: bool = True

    created_at: datetime

    # =====================================================
    # DISCOUNTED PRICE
    # =====================================================

    @computed_field
    @property
    def discounted_price(
        self,
    ) -> float:

        return round(
            self.price
            - (
                self.price
                * self.discount
                / 100
            ),
            2,
        )

    # =====================================================
    # CGST
    # =====================================================

    @computed_field
    @property
    def cgst_amount(
        self,
    ) -> float:

        if self.tax_type != "GST":
            return 0.0

        return round(
            self.discounted_price
            * self.cgst_rate
            / 100,
            2,
        )

    # =====================================================
    # SGST
    # =====================================================

    @computed_field
    @property
    def sgst_amount(
        self,
    ) -> float:

        if self.tax_type != "GST":
            return 0.0

        return round(
            self.discounted_price
            * self.sgst_rate
            / 100,
            2,
        )

    # =====================================================
    # VAT RATE
    # =====================================================

    @computed_field
    @property
    def vat_rate(
        self,
    ) -> float:

        if self.tax_type != "VAT":
            return 0.0

        return round(
            self.tax,
            2,
        )

    # =====================================================
    # VAT AMOUNT
    # =====================================================

    @computed_field
    @property
    def vat_amount(
        self,
    ) -> float:

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
    def total_tax_amount(
        self,
    ) -> float:

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
    def total_price(
        self,
    ) -> float:

        return round(
            self.discounted_price
            + self.total_tax_amount,
            2,
        )

    model_config = ConfigDict(
        from_attributes=True,
    )


class TaxHistoryOut(
    BaseModel
):

    id: int

    old_tax: float

    new_tax: float

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )