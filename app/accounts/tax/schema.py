from pydantic import BaseModel, Field
from typing import Optional


class TaxBillingBase(BaseModel):
    default_tax_rate:      float = Field(default=5.0,  ge=0)
    cgst:                  float = Field(default=2.5,  ge=0)
    sgst:                  float = Field(default=2.5,  ge=0)
    service_charge:        float = Field(default=0.0,  ge=0)
    bill_footer_message:   str   = "Thank you for dining with us!"
    enable_service_charge: bool  = False
    enable_tax:            bool  = True
    round_off_bill:        bool  = True


class TaxBillingCreate(TaxBillingBase):
    branch_id: int


class TaxBillingUpdate(BaseModel):
    default_tax_rate:      Optional[float] = None
    cgst:                  Optional[float] = None
    sgst:                  Optional[float] = None
    service_charge:        Optional[float] = None
    bill_footer_message:   Optional[str]   = None
    enable_service_charge: Optional[bool]  = None
    enable_tax:            Optional[bool]  = None
    round_off_bill:        Optional[bool]  = None


class TaxBillingOut(TaxBillingBase):
    id:        int
    client_id: int
    branch_id: int

    model_config = {"from_attributes": True}
