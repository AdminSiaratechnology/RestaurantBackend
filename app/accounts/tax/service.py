# app/accounts/tax/service.py

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.branch.model import Branch
from app.accounts.tax.model import TaxBillingSetting
from app.core.tax import get_branch_tax_config


async def create_tax_settings_service(
    db,
    data,
    user
):
    # Validate branch
    branch_res = await db.execute(
        select(Branch).where(
            Branch.id == data.branch_id,
            Branch.client_id == user.id
        )
    )

    branch = branch_res.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found"
        )

    # Check existing settings
    existing_res = await db.execute(
        select(TaxBillingSetting).where(
            TaxBillingSetting.branch_id == data.branch_id
        )
    )

    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Settings already exist for this branch"
        )

    enable_service = (
        data.enable_service_charge
        or (data.service_charge or 0) > 0
    )

    tax_config = get_branch_tax_config(
        country=branch.country,
        tax_rate=data.default_tax_rate,
        decimal_places=branch.decimal_places if hasattr(branch, 'decimal_places') else 2,
    )

    setting = TaxBillingSetting(
        client_id=user.id,
        branch_id=data.branch_id,
        default_tax_rate=tax_config["tax_rate"],
        cgst=tax_config["cgst_rate"],
        sgst=tax_config["sgst_rate"],
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


async def get_tax_settings_service(
    db,
    branch_id,
    user
):
    res = await db.execute(
        select(TaxBillingSetting)
        .join(
            Branch,
            Branch.id == TaxBillingSetting.branch_id
        )
        .where(
            TaxBillingSetting.branch_id == branch_id,
            Branch.client_id == user.id
        )
    )

    setting = res.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=404,
            detail="Tax settings not found for this branch"
        )

    return setting


async def update_tax_settings_service(
    db,
    branch_id,
    data,
    user
):
    res = await db.execute(
        select(TaxBillingSetting)
        .join(
            Branch,
            Branch.id == TaxBillingSetting.branch_id
        )
        .where(
            TaxBillingSetting.branch_id == branch_id,
            Branch.client_id == user.id
        )
    )

    setting = res.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=404,
            detail="Tax settings not found for this branch"
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    if "default_tax_rate" in update_data:
        branch_res = await db.execute(select(Branch).where(Branch.id == branch_id))
        branch = branch_res.scalar_one_or_none()
        tax_cfg = get_branch_tax_config(
            country=branch.country if branch else None,
            tax_rate=update_data["default_tax_rate"],
            decimal_places=branch.decimal_places if branch and hasattr(branch, 'decimal_places') else 2,
        )
        update_data["cgst"] = tax_cfg["cgst_rate"]
        update_data["sgst"] = tax_cfg["sgst_rate"]

    if (
        update_data.get("service_charge", 0) > 0
        and "enable_service_charge"
        not in update_data
    ):
        update_data["enable_service_charge"] = True

    for key, value in update_data.items():
        setattr(setting, key, value)

    await db.commit()
    await db.refresh(setting)

    return setting