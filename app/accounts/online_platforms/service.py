# app/online_platforms/service.py

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.online_platforms.model import OnlinePlatformConnection
from app.accounts.online_platforms.schema import (
    OnlinePlatformConnectionCreate,
    OnlinePlatformConnectionUpdate,
)


class OnlinePlatformConnectionService:

    # =========================================================
    # GET BY ID
    # =========================================================

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        connection_id: int,
    ) -> Optional[OnlinePlatformConnection]:

        result = await db.execute(
            select(OnlinePlatformConnection).where(
                OnlinePlatformConnection.id == connection_id
            )
        )

        return result.scalar_one_or_none()

    # =========================================================
    # GET BY BRANCH + PLATFORM
    # =========================================================

    @staticmethod
    async def get_by_branch_platform(
        db: AsyncSession,
        branch_id: int,
        platform: str,
    ) -> Optional[OnlinePlatformConnection]:

        result = await db.execute(
            select(OnlinePlatformConnection).where(
                OnlinePlatformConnection.branch_id == branch_id,
                OnlinePlatformConnection.platform == platform,
            )
        )

        return result.scalar_one_or_none()

    # =========================================================
    # CREATE
    # =========================================================

    @staticmethod
    async def create(
        db: AsyncSession,
        data: OnlinePlatformConnectionCreate,
    ) -> OnlinePlatformConnection:

        # -----------------------------------------------------
        # Check duplicate
        # -----------------------------------------------------

        existing = await OnlinePlatformConnectionService.get_by_branch_platform(
            db=db,
            branch_id=data.branch_id,
            platform=data.platform,
        )

        if existing:
            raise ValueError(
                f"{data.platform} connection already exists "
                f"for branch {data.branch_id}"
            )

        # -----------------------------------------------------
        # Create
        # -----------------------------------------------------

        connection = OnlinePlatformConnection(
            branch_id=data.branch_id,
            platform=data.platform,
            display_name=data.display_name,
            connection_status=data.connection_status,
            is_active=data.is_active,
            api_key=data.api_key,
            api_secret=data.api_secret,
            access_token=data.access_token,
            refresh_token=data.refresh_token,
            webhook_secret=data.webhook_secret,
            platform_restaurant_id=data.platform_restaurant_id,
            platform_store_id=data.platform_store_id,
            config=data.config,
        )

        db.add(connection)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise ValueError(
                "A connection for this branch and platform "
                "already exists."
            )

        await db.refresh(connection)

        return connection

    # =========================================================
    # UPDATE
    # =========================================================

    @staticmethod
    async def update(
        db: AsyncSession,
        connection: OnlinePlatformConnection,
        data: OnlinePlatformConnectionUpdate,
    ) -> OnlinePlatformConnection:

        update_data = data.model_dump(
            exclude_unset=True,
        )

        # -----------------------------------------------------
        # Platform change
        # -----------------------------------------------------

        new_platform = update_data.get("platform")

        if (
            new_platform is not None
            and new_platform != connection.platform
        ):

            existing = (
                await OnlinePlatformConnectionService.get_by_branch_platform(
                    db=db,
                    branch_id=connection.branch_id,
                    platform=new_platform,
                )
            )

            if existing and existing.id != connection.id:
                raise ValueError(
                    f"{new_platform} connection already exists "
                    f"for branch {connection.branch_id}"
                )

        # -----------------------------------------------------
        # Apply changes
        # -----------------------------------------------------

        for field, value in update_data.items():
            setattr(
                connection,
                field,
                value,
            )

        # -----------------------------------------------------
        # Connected timestamp
        # -----------------------------------------------------

        if (
            update_data.get("connection_status")
            == "connected"
        ):
            connection.last_connected_at = datetime.now(
                timezone.utc
            )

            connection.last_error = None

        # -----------------------------------------------------
        # Error status
        # -----------------------------------------------------

        if (
            update_data.get("connection_status")
            == "error"
        ):
            if not update_data.get("last_error"):
                connection.last_error = (
                    connection.last_error
                    or "Connection error"
                )

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise ValueError(
                "Unable to update platform connection."
            )

        await db.refresh(connection)

        return connection

    # =========================================================
    # LIST
    # =========================================================

    @staticmethod
    async def list(
        db: AsyncSession,
        branch_id: Optional[int] = None,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[OnlinePlatformConnection]:

        query = select(
            OnlinePlatformConnection
        ).order_by(
            OnlinePlatformConnection.id.desc()
        )

        if branch_id is not None:
            query = query.where(
                OnlinePlatformConnection.branch_id == branch_id
            )

        if platform is not None:
            query = query.where(
                OnlinePlatformConnection.platform == platform
            )

        if is_active is not None:
            query = query.where(
                OnlinePlatformConnection.is_active == is_active
            )

        result = await db.execute(query)

        return list(
            result.scalars().all()
        )

    # =========================================================
    # DELETE
    # =========================================================

    @staticmethod
    async def delete(
        db: AsyncSession,
        connection: OnlinePlatformConnection,
    ) -> None:

        await db.delete(connection)

        await db.commit()