from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.accounts.branch.model import Branch
from app.accounts.offer.model import Offer
from app.db.config import SessionDep
from app.accounts.legaldetails.model import LegalCompliance
from app.accounts.legaldetails.schema import (
    LegalComplianceCreate,
    LegalComplianceResponse
)

from app.accounts.deps import access_one

router = APIRouter(
    prefix="/legal_compliance",
    tags=["Legal Compliance"]
)


@router.post(
    "/create-update",
    response_model=LegalComplianceResponse
)
async def create_update_legal_compliance(
    data: LegalComplianceCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    try:
        user = current["user"]
        role = current["role"]

        # STAFF restriction
        if role == "staff":
            if user.branch_id != data.branch_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access your own branch"
                )

        # ✅ Branch validation
        branch_result = await db.execute(
            select(Branch).where(
                Branch.id == data.branch_id
            )
        )

        branch = branch_result.scalar_one_or_none()

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Branch not found"
            )


        # ✅ Check existing data
        existing_result = await db.execute(
            select(LegalCompliance).where(
                LegalCompliance.branch_id == data.branch_id
            )
        )

        existing = existing_result.scalar_one_or_none()

        # ================= UPDATE =================
        if existing:
            existing.gst_vat_number = data.gst_vat_number
            existing.fssai_license_no = data.fssai_license_no

            await db.commit()
            await db.refresh(existing)

            return existing

        # ================= CREATE =================
        new_data = LegalCompliance(
            branch_id=data.branch_id,
            gst_vat_number=data.gst_vat_number,
            fssai_license_no=data.fssai_license_no
        )

        db.add(new_data)

        await db.commit()
        await db.refresh(new_data)

        return new_data

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



@router.get(
    "/{branch_id}",
    response_model=LegalComplianceResponse
)
async def get_legal_compliance(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    try:

        # ==========================================
        # CHECK BRANCH EXISTS
        # ==========================================
        branch_result = await db.execute(
            select(Branch).where(
                Branch.id == branch_id
            )
        )

        branch = branch_result.scalar_one_or_none()

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Branch not found"
            )

        # ==========================================
        # GET LEGAL DATA
        # ==========================================
        data_result = await db.execute(
            select(LegalCompliance).where(
                LegalCompliance.branch_id == branch_id
            )
        )

        data = data_result.scalar_one_or_none()

        if not data:
            raise HTTPException(
                status_code=404,
                detail="Data not found"
            )

        return data

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.put(
    "/update/{branch_id}",
    response_model=LegalComplianceResponse
)
async def update_legal_compliance(
    branch_id: int,
    data: LegalComplianceCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    try:

        # ==========================================
        # CHECK BRANCH EXISTS
        # ==========================================
        branch_result = await db.execute(
            select(Branch).where(
                Branch.id == branch_id
            )
        )

        branch = branch_result.scalar_one_or_none()

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Branch not found"
            )

        # ==========================================
        # GET EXISTING DATA
        # ==========================================
        data_result = await db.execute(
            select(LegalCompliance).where(
                LegalCompliance.branch_id == branch_id
            )
        )

        legal_data = data_result.scalar_one_or_none()

        if not legal_data:
            raise HTTPException(
                status_code=404,
                detail="Legal compliance data not found"
            )

        # ==========================================
        # UPDATE DATA
        # ==========================================
        legal_data.gst_vat_number = data.gst_vat_number
        legal_data.fssai_license_no = data.fssai_license_no

        await db.commit()
        await db.refresh(legal_data)

        return legal_data

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.delete(
    "/delete/{branch_id}"
)
async def delete_legal_compliance(
    branch_id: int,
    db: SessionDep,
    current=Depends(access_one)
):
    try:

        # ==========================================
        # CHECK BRANCH EXISTS
        # ==========================================
        branch_result = await db.execute(
            select(Branch).where(
                Branch.id == branch_id
            )
        )

        branch = branch_result.scalar_one_or_none()

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Branch not found"
            )

        # ==========================================
        # GET LEGAL DATA
        # ==========================================
        data_result = await db.execute(
            select(LegalCompliance).where(
                LegalCompliance.branch_id == branch_id
            )
        )

        legal_data = data_result.scalar_one_or_none()

        if not legal_data:
            raise HTTPException(
                status_code=404,
                detail="Legal compliance data not found"
            )

        # ==========================================
        # DELETE
        # ==========================================
        await db.delete(legal_data)

        await db.commit()

        return {
            "success": True,
            "message": "Legal compliance deleted successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )