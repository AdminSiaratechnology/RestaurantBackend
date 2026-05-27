# app/accounts/legaldetails/schema.py

from pydantic import BaseModel
from typing import Optional


class LegalComplianceCreate(BaseModel):
    branch_id: int
    gst_vat_number: Optional[str] = None
    fssai_license_no: Optional[str] = None


class LegalComplianceResponse(BaseModel):
    id: int
    branch_id: int
    gst_vat_number: Optional[str]
    fssai_license_no: Optional[str]

    class Config:
        from_attributes = True