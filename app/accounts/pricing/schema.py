from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, computed_field


class PricingBase(BaseModel):
    item_id: int

    # ✅ MARKED POINTS
    price: float = Field(gt=0)
    cost_price: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=5, ge=0)
    calories: int | None = None

    is_active: bool = True


class PricingCreate(PricingBase):
    branch_id: int


class PricingUpdate(BaseModel):
    price: float | None = Field(default=None, gt=0)
    cost_price: float | None = Field(default=None, ge=0)
    discount: float | None = Field(default=None, ge=0)
    tax_rate: float | None = Field(default=None, ge=0)
    calories: int | None = None

    is_active: bool | None = None


class PricingOut(BaseModel):
    id: int

    client_id: int
    branch_id: int | None = None
    item_id: int

    # ✅ MARKED POINTS
    price: float
    cost_price: float | None = 0.0
    discount: float | None = 0.0
    tax_rate: float | None = 5.0
    calories: int | None = None

    is_active: bool | None = True

    created_at: datetime

    @computed_field
    @property
    def total_price(self) -> float:
        """
        Compute final price with discount and tax applied.
        Formula:
          discounted = price - (price * discount% / 100)
          total      = discounted + (discounted * tax_rate% / 100)
        """
        base = self.price or 0.0
        disc = self.discount or 0.0
        tax  = self.tax_rate or 0.0
        discounted = base - (base * disc / 100)
        total = discounted + (discounted * tax / 100)
        return round(total, 2)

    model_config = ConfigDict(
        from_attributes=True
    )