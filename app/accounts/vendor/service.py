from sqlalchemy import (
    and_,
    or_,
    select,
)

from app.db.config import SessionDep

from app.accounts.vendor.model import Vendor

from app.accounts.vendor.schema import (
    VendorCreate,
    VendorUpdate,
)


class VendorService:

    # =========================================================
    # GENERATE CLIENT-WISE VENDOR CODE
    # =========================================================

    @staticmethod
    async def generate_vendor_code(
        db: SessionDep,
        client_id: int,
    ) -> str:

        result = await db.execute(
            select(Vendor)
            .where(
                Vendor.client_id == client_id
            )
            .order_by(
                Vendor.id.desc()
            )
            .limit(1)
        )

        last_vendor = result.scalar_one_or_none()

        if not last_vendor:
            return "VEND0001"

        try:
            last_number = int(
                last_vendor.vendor_code.replace(
                    "VEND",
                    "",
                )
            )
        except (
            ValueError,
            AttributeError,
        ):
            last_number = 0

        return f"VEND{last_number + 1:04d}"

    # =========================================================
    # CREATE
    # =========================================================

    @staticmethod
    async def create_vendor(
        db: SessionDep,
        payload: VendorCreate,
        client_id: int,
    ):

        vendor_code = (
            await VendorService.generate_vendor_code(
                db=db,
                client_id=client_id,
            )
        )

        vendor_data = payload.model_dump(
            mode="python"
        )

        # -----------------------------------------------------
        # ENUM → STRING
        # -----------------------------------------------------

        for field in (
            "vendor_type",
            "payment_method",
        ):
            value = vendor_data.get(field)

            if value is not None and hasattr(
                value,
                "value",
            ):
                vendor_data[field] = value.value

        vendor = Vendor(
            client_id=client_id,
            vendor_code=vendor_code,
            **vendor_data,
        )

        db.add(vendor)

        try:

            await db.commit()

        except Exception:

            await db.rollback()

            raise

        await db.refresh(vendor)

        return vendor

    # =========================================================
    # GET SINGLE
    # =========================================================

    @staticmethod
    async def get_vendor(
        db: SessionDep,
        vendor_id: int,
        client_id: int,
    ):

        result = await db.execute(
            select(Vendor).where(
                and_(
                    Vendor.id == vendor_id,
                    Vendor.client_id == client_id,
                )
            )
        )

        return result.scalar_one_or_none()

    # =========================================================
    # GET ALL
    # =========================================================

    @staticmethod
    async def get_all_vendors(
        db: SessionDep,
        client_id: int,
        branch_id: int | None = None,
    ):

        conditions = [
            Vendor.client_id == client_id
        ]

        # Branch is optional filtering only.
        # It is NOT authorization.

        if branch_id is not None:
            conditions.append(
                or_(
                    Vendor.branch_id == branch_id,
                    Vendor.branch_id.is_(None),
                )
            )

        result = await db.execute(
            select(Vendor)
            .where(
                and_(*conditions)
            )
            .order_by(
                Vendor.id.desc()
            )
        )

        return result.scalars().all()

    # =========================================================
    # UPDATE
    # =========================================================

    @staticmethod
    async def update_vendor(
        db: SessionDep,
        vendor_id: int,
        payload: VendorUpdate,
        client_id: int,
    ):

        result = await db.execute(
            select(Vendor).where(
                and_(
                    Vendor.id == vendor_id,
                    Vendor.client_id == client_id,
                )
            )
        )

        vendor = result.scalar_one_or_none()

        if not vendor:
            return None

        update_data = payload.model_dump(
            exclude_unset=True,
            exclude_none=False,
            mode="python",
        )

        # -----------------------------------------------------
        # ENUM → STRING
        # -----------------------------------------------------

        for field in (
            "vendor_type",
            "payment_method",
            "status",
        ):

            value = update_data.get(field)

            if value is not None and hasattr(
                value,
                "value",
            ):
                update_data[field] = value.value

        # -----------------------------------------------------
        # NEVER allow client_id modification
        # -----------------------------------------------------

        update_data.pop(
            "client_id",
            None,
        )

        # Vendor code also cannot be changed.

        update_data.pop(
            "vendor_code",
            None,
        )

        for key, value in update_data.items():

            setattr(
                vendor,
                key,
                value,
            )

        try:

            await db.commit()

        except Exception:

            await db.rollback()

            raise

        await db.refresh(vendor)

        return vendor

    # =========================================================
    # SOFT DELETE
    # =========================================================

    @staticmethod
    async def delete_vendor(
        db: SessionDep,
        vendor_id: int,
        client_id: int,
    ) -> bool:

        result = await db.execute(
            select(Vendor).where(
                and_(
                    Vendor.id == vendor_id,
                    Vendor.client_id == client_id,
                )
            )
        )

        vendor = result.scalar_one_or_none()

        if not vendor:
            return False

        # -----------------------------------------------------
        # DO NOT HARD DELETE PURCHASE-RELATED VENDOR
        # -----------------------------------------------------

        vendor.status = "inactive"

        try:

            await db.commit()

        except Exception:

            await db.rollback()

            raise

        return True

    # =========================================================
    # SEARCH
    # =========================================================

    @staticmethod
    async def search_vendors(
        db: SessionDep,
        q: str,
        client_id: int,
    ):

        search = f"%{q.strip()}%"

        result = await db.execute(
            select(Vendor)
            .where(
                and_(
                    # -----------------------------------------
                    # CLIENT SECURITY CONDITION
                    # -----------------------------------------

                    Vendor.client_id == client_id,

                    # -----------------------------------------
                    # SEARCH
                    # -----------------------------------------

                    or_(
                        Vendor.vendor_name.ilike(
                            search
                        ),
                        Vendor.vendor_code.ilike(
                            search
                        ),
                        Vendor.mobile.ilike(
                            search
                        ),
                        Vendor.email.ilike(
                            search
                        ),
                    ),
                )
            )
            .order_by(
                Vendor.vendor_name.asc()
            )
        )

        return result.scalars().all()