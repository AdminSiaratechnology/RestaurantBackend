from sqlalchemy import select
from app.db.config import SessionDep

from app.accounts.vendor.model import Vendor
from app.accounts.vendor.schema import (
    VendorCreate,
    VendorUpdate
)


class VendorService:

    @staticmethod
    async def generate_vendor_code(db: SessionDep):
        result = await db.execute(
            select(Vendor)
            .order_by(Vendor.id.desc())
            .limit(1)
        )

        last_vendor = result.scalar_one_or_none()

        if not last_vendor:
            return "VEND0001"

        last_number = int(
            last_vendor.vendor_code.replace("VEND", "")
        )

        return f"VEND{last_number + 1:04d}"

    @staticmethod
    async def create_vendor(
        db: SessionDep,
        payload: VendorCreate
    ):
        vendor = Vendor(
            vendor_code=await VendorService.generate_vendor_code(db),
            **payload.model_dump()
        )

        db.add(vendor)

        await db.commit()
        await db.refresh(vendor)

        return vendor

    @staticmethod
    async def get_vendor(
        db: SessionDep,
        vendor_id: int
    ):
        result = await db.execute(
            select(Vendor).where(
                Vendor.id == vendor_id
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_vendors(
        db: SessionDep
    ):
        result = await db.execute(
            select(Vendor)
        )

        return result.scalars().all()

    @staticmethod
    async def update_vendor(
        db: SessionDep,
        vendor_id: int,
        payload: VendorUpdate
    ):
        result = await db.execute(
            select(Vendor).where(
                Vendor.id == vendor_id
            )
        )

        vendor = result.scalar_one_or_none()

        if not vendor:
            return None

        update_data = payload.model_dump(
            exclude_unset=True
        )

        for key, value in update_data.items():
            setattr(vendor, key, value)

        await db.commit()
        await db.refresh(vendor)

        return vendor

    @staticmethod
    async def delete_vendor(
        db: SessionDep,
        vendor_id: int
    ):
        result = await db.execute(
            select(Vendor).where(
                Vendor.id == vendor_id
            )
        )

        vendor = result.scalar_one_or_none()

        print("FOUND:", vendor)

        if not vendor:
            return False

        await db.delete(vendor)

        print("DELETE CALLED")

        await db.commit()

        print("COMMIT DONE")

        return True