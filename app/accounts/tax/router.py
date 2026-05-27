from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.db.config import SessionDep
from app.accounts.deps import get_current_user, access_three
from app.accounts.branch.model import Branch
from app.accounts.tax.model import TaxBillingSetting
from app.accounts.tax.schema import TaxBillingCreate, TaxBillingUpdate, TaxBillingOut

router = APIRouter(prefix="/tax_billing", tags=["Tax Billing"])


# ─── CREATE ──────────────────────────────────────────────────────────────────
@router.post("/", response_model=TaxBillingOut)
async def create_tax_settings(
    data: TaxBillingCreate,
    db: SessionDep,
    current=Depends(access_three)
):
    user = current["user"]

    # Validate branch belongs to this client
    branch_res = await db.execute(
        select(Branch).where(
            Branch.id == data.branch_id,
            Branch.client_id == user.id
        )
    )
    branch = branch_res.scalar_one_or_none()
    if not branch:
        raise HTTPException(404, "Branch not found")

    # Prevent duplicate settings per branch
    existing_res = await db.execute(
        select(TaxBillingSetting).where(
            TaxBillingSetting.branch_id == data.branch_id
        )
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(400, "Settings already exist for this branch")

    enable_service = data.enable_service_charge or (data.service_charge or 0) > 0

    setting = TaxBillingSetting(
        client_id=user.id,
        branch_id=data.branch_id,
        default_tax_rate=data.default_tax_rate,
        cgst=data.default_tax_rate / 2,
        sgst=data.default_tax_rate / 2,
        service_charge=data.service_charge,
        bill_footer_message=data.bill_footer_message,
        enable_service_charge=enable_service,
        enable_tax=data.enable_tax,
        round_off_bill=data.round_off_bill,
    )

    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


# ─── GET ─────────────────────────────────────────────────────────────────────
@router.get("/{branch_id}", response_model=TaxBillingOut)
async def get_tax_settings(
    branch_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):
    user = current["user"]

    res = await db.execute(
        select(TaxBillingSetting)
        .join(Branch, Branch.id == TaxBillingSetting.branch_id)
        .where(
            TaxBillingSetting.branch_id == branch_id,
            Branch.client_id == user.id
        )
    )
    setting = res.scalar_one_or_none()
    if not setting:
        raise HTTPException(404, "Tax settings not found for this branch")
    return setting


# ─── UPDATE ──────────────────────────────────────────────────────────────────
@router.put("/{branch_id}", response_model=TaxBillingOut)
async def update_tax_settings(
    branch_id: int,
    data: TaxBillingUpdate,
    db: SessionDep,
    current=Depends(access_three)
):
    user = current["user"]

    res = await db.execute(
        select(TaxBillingSetting)
        .join(Branch, Branch.id == TaxBillingSetting.branch_id)
        .where(
            TaxBillingSetting.branch_id == branch_id,
            Branch.client_id == user.id
        )
    )
    setting = res.scalar_one_or_none()
    if not setting:
        raise HTTPException(404, "Tax settings not found for this branch")

    update_data = data.model_dump(exclude_unset=True)
    if "default_tax_rate" in update_data:
        update_data["cgst"] = update_data["default_tax_rate"] / 2
        update_data["sgst"] = update_data["default_tax_rate"] / 2

    if (
        update_data.get("service_charge", 0) > 0
        and "enable_service_charge" not in update_data
    ):
        update_data["enable_service_charge"] = True

    for key, value in update_data.items():
        setattr(setting, key, value)

    await db.commit()
    await db.refresh(setting)
    return setting
