from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.branch.model import Branch
from app.accounts.legaldetails.model import LegalCompliance
from app.accounts.legaldetails.schema import LegalComplianceCreate


class LegalComplianceService:

    @staticmethod
    async def create_or_update(
        db,
        payload: LegalComplianceCreate
    ):
        branch = await db.get(
            Branch,
            payload.branch_id
        )

        if not branch:
            raise HTTPException(
                404,
                "Branch not found"
            )

        result = await db.execute(
            select(LegalCompliance).where(
                LegalCompliance.branch_id == payload.branch_id
            )
        )

        legal = result.scalar_one_or_none()

        if legal:

            legal.gst_vat_number = payload.gst_vat_number
            legal.fssai_license_no = payload.fssai_license_no

            await db.commit()
            await db.refresh(legal)

            return legal

        legal = LegalCompliance(
            branch_id=payload.branch_id,
            gst_vat_number=payload.gst_vat_number,
            fssai_license_no=payload.fssai_license_no
        )

        db.add(legal)

        await db.commit()
        await db.refresh(legal)

        return legal

    @staticmethod
    async def get_by_branch(
        db,
        branch_id: int
    ):
        branch = await db.get(
            Branch,
            branch_id
        )

        if not branch:
            raise HTTPException(
                404,
                "Branch not found"
            )

        result = await db.execute(
            select(LegalCompliance).where(
                LegalCompliance.branch_id == branch_id
            )
        )

        legal = result.scalar_one_or_none()

        if not legal:
            raise HTTPException(
                404,
                "Legal compliance data not found"
            )

        return legal

    @staticmethod
    async def update(
        db,
        branch_id: int,
        payload: LegalComplianceCreate
    ):
        legal = await LegalComplianceService.get_by_branch(
            db,
            branch_id
        )

        legal.gst_vat_number = payload.gst_vat_number
        legal.fssai_license_no = payload.fssai_license_no

        await db.commit()
        await db.refresh(legal)

        return legal

    @staticmethod
    async def delete(
        db,
        branch_id: int
    ):
        legal = await LegalComplianceService.get_by_branch(
            db,
            branch_id
        )

        await db.delete(legal)

        await db.commit()

        return {
            "success": True,
            "message": "Legal compliance deleted successfully"
        }