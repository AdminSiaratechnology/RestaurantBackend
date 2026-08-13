"""
app/accounts/settings/router.py

FastAPI REST Router for System & Restaurant Settings.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import SessionDep
from app.accounts.deps import get_current_user
from app.accounts.client.model import Client
from app.accounts.branch.model import Branch
from app.accounts.tax.model import TaxBillingSetting
from app.accounts.legaldetails.model import LegalCompliance


router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


class SettingsResponse(BaseModel):
    id: int = 1
    client_id: Optional[int] = None
    restaurant_name: Optional[str] = ""
    restaurant_address: Optional[str] = ""
    restaurant_phone: Optional[str] = ""
    restaurant_email: Optional[str] = ""
    restaurant_gst: Optional[str] = ""
    restaurant_fssai: Optional[str] = ""
    service_charge_percent: float = 0.0
    default_tax_rate: float = 0.0
    enable_service_charge: bool = False
    enable_tax: bool = True
    round_off_bill: bool = True
    currency: str = "INR"
    currency_symbol: str = "₹"
    bill_footer_message: Optional[str] = "Thank you for dining with us!"
    zomato_restaurant_id: Optional[str] = ""
    swiggy_restaurant_id: Optional[str] = ""
    petpooja_token: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True, extra="allow")


class SettingsUpdate(BaseModel):
    restaurant_name: Optional[str] = None
    restaurant_address: Optional[str] = None
    restaurant_phone: Optional[str] = None
    restaurant_email: Optional[str] = None
    restaurant_gst: Optional[str] = None
    restaurant_fssai: Optional[str] = None
    service_charge_percent: Optional[float] = None
    default_tax_rate: Optional[float] = None
    enable_service_charge: Optional[bool] = None
    enable_tax: Optional[bool] = None
    round_off_bill: Optional[bool] = None
    currency: Optional[str] = None
    currency_symbol: Optional[str] = None
    bill_footer_message: Optional[str] = None
    zomato_restaurant_id: Optional[str] = None
    swiggy_restaurant_id: Optional[str] = None
    petpooja_token: Optional[str] = None

    model_config = ConfigDict(extra="allow")


async def _fetch_settings_data(
    db: AsyncSession,
    settings_id: int,
    client_id: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:

    resolved_client_id = client_id or settings_id
    client = None
    branch = None
    tax_setting = None
    legal_setting = None

    if resolved_client_id:
        res = await db.execute(select(Client).where(Client.id == resolved_client_id))
        client = res.scalar_one_or_none()

    if branch_id:
        res_b = await db.execute(select(Branch).where(Branch.id == branch_id))
        branch = res_b.scalar_one_or_none()
    elif resolved_client_id:
        res_b = await db.execute(select(Branch).where(Branch.client_id == resolved_client_id))
        branch = res_b.scalars().first()

    if branch:
        res_t = await db.execute(select(TaxBillingSetting).where(TaxBillingSetting.branch_id == branch.id))
        tax_setting = res_t.scalar_one_or_none()

        res_l = await db.execute(select(LegalCompliance).where(LegalCompliance.branch_id == branch.id))
        legal_setting = res_l.scalar_one_or_none()

    return {
        "id": settings_id,
        "client_id": resolved_client_id,
        "restaurant_name": (branch.name if branch else None) or (client.name if client else "") or "My Restaurant",
        "restaurant_address": (branch.address if branch else "") or "",
        "restaurant_phone": (getattr(branch, "phone", None) if branch else "") or "",
        "restaurant_email": (client.email if client else "") or "",
        "restaurant_gst": (legal_setting.gst_vat_number if legal_setting else "") or "",
        "restaurant_fssai": (legal_setting.fssai_license_no if legal_setting else "") or "",
        "service_charge_percent": (tax_setting.service_charge if tax_setting else 0.0) or 0.0,
        "default_tax_rate": (tax_setting.default_tax_rate if tax_setting else 5.0) or 5.0,
        "enable_service_charge": (tax_setting.enable_service_charge if tax_setting else False),
        "enable_tax": (tax_setting.enable_tax if tax_setting else True),
        "round_off_bill": (tax_setting.round_off_bill if tax_setting else True),
        "currency": "INR",
        "currency_symbol": "₹",
        "bill_footer_message": (tax_setting.bill_footer_message if tax_setting else "Thank you for dining with us!") or "Thank you for dining with us!",
        "zomato_restaurant_id": "",
        "swiggy_restaurant_id": "",
        "petpooja_token": "",
    }


@router.get(
    "/{settings_id}",
    response_model=SettingsResponse,
    summary="Get Settings by ID",
)
async def get_settings_by_id(
    settings_id: int,
    db: SessionDep,
    client_id: Optional[int] = Query(None, description="Optional Client ID filter"),
    branch_id: Optional[int] = Query(None, description="Optional Branch ID filter"),
    current=Depends(get_current_user),
):
    return await _fetch_settings_data(
        db=db,
        settings_id=settings_id,
        client_id=client_id,
        branch_id=branch_id,
    )


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get Settings",
)
async def get_settings(
    db: SessionDep,
    client_id: Optional[int] = Query(None, description="Optional Client ID filter"),
    branch_id: Optional[int] = Query(None, description="Optional Branch ID filter"),
    current=Depends(get_current_user),
):
    cid = client_id or 1
    return await _fetch_settings_data(
        db=db,
        settings_id=cid,
        client_id=cid,
        branch_id=branch_id,
    )


@router.put(
    "/{settings_id}",
    response_model=SettingsResponse,
    summary="Update Settings by ID",
)
async def update_settings_by_id(
    settings_id: int,
    payload: SettingsUpdate,
    db: SessionDep,
    client_id: Optional[int] = Query(None, description="Optional Client ID filter"),
    branch_id: Optional[int] = Query(None, description="Optional Branch ID filter"),
    current=Depends(get_current_user),
):
    data = await _fetch_settings_data(
        db=db,
        settings_id=settings_id,
        client_id=client_id,
        branch_id=branch_id,
    )
    update_dict = payload.model_dump(exclude_unset=True)
    data.update(update_dict)
    return data


@router.put(
    "",
    response_model=SettingsResponse,
    summary="Update Settings",
)
async def update_settings(
    payload: SettingsUpdate,
    db: SessionDep,
    client_id: Optional[int] = Query(None, description="Optional Client ID filter"),
    branch_id: Optional[int] = Query(None, description="Optional Branch ID filter"),
    current=Depends(get_current_user),
):
    cid = client_id or 1
    data = await _fetch_settings_data(
        db=db,
        settings_id=cid,
        client_id=cid,
        branch_id=branch_id,
    )
    update_dict = payload.model_dump(exclude_unset=True)
    data.update(update_dict)
    return data
