# app/online_item_mappings/service.py

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.online_item_mappings.model import OnlinePlatformItemMapping
from app.accounts.online_item_mappings.schema import (
    OnlinePlatformItemMappingCreate,
    OnlinePlatformItemMappingUpdate,
)

from app.accounts.item.model import Item
from app.accounts.online_platforms.model import OnlinePlatformConnection


class OnlinePlatformItemMappingService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------
    # GET BY ID
    # ---------------------------------------------------------

    async def get_by_id(
        self,
        mapping_id: int
    ) -> OnlinePlatformItemMapping:

        result = await self.db.execute(
            select(OnlinePlatformItemMapping)
            .where(
                OnlinePlatformItemMapping.id == mapping_id
            )
        )

        mapping = result.scalar_one_or_none()

        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item mapping not found"
            )

        return mapping

    # ---------------------------------------------------------
    # GET BY INTERNAL ITEM
    # ---------------------------------------------------------

    async def get_by_connection_and_item(
        self,
        connection_id: int,
        item_id: int
    ):

        result = await self.db.execute(
            select(OnlinePlatformItemMapping)
            .where(
                OnlinePlatformItemMapping.online_platform_connection_id
                == connection_id,
                OnlinePlatformItemMapping.item_id
                == item_id
            )
        )

        return result.scalar_one_or_none()

    # ---------------------------------------------------------
    # GET BY PLATFORM ITEM
    # ---------------------------------------------------------

    async def get_by_connection_and_platform_item(
        self,
        connection_id: int,
        platform_item_id: str
    ):

        result = await self.db.execute(
            select(OnlinePlatformItemMapping)
            .where(
                OnlinePlatformItemMapping.online_platform_connection_id
                == connection_id,

                OnlinePlatformItemMapping.platform_item_id
                == platform_item_id
            )
        )

        return result.scalar_one_or_none()

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    async def create(
        self,
        data: OnlinePlatformItemMappingCreate
    ):

        # -----------------------------------------------------
        # CHECK CONNECTION
        # -----------------------------------------------------

        connection_result = await self.db.execute(
            select(OnlinePlatformConnection)
            .where(
                OnlinePlatformConnection.id
                == data.online_platform_connection_id
            )
        )

        connection = connection_result.scalar_one_or_none()

        if not connection:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Online platform connection not found"
            )

        # -----------------------------------------------------
        # CHECK ITEM
        # -----------------------------------------------------

        item_result = await self.db.execute(
            select(Item)
            .where(
                Item.id == data.item_id
            )
        )

        item = item_result.scalar_one_or_none()

        if not item:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Internal item not found"
            )

        # -----------------------------------------------------
        # BRANCH VALIDATION
        # -----------------------------------------------------

        if item.branch_id != connection.branch_id:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Internal item does not belong to "
                    "the branch of this platform connection"
                )
            )

        # -----------------------------------------------------
        # CHECK INTERNAL ITEM DUPLICATE
        # -----------------------------------------------------

        existing_item = await self.get_by_connection_and_item(
            connection_id=data.online_platform_connection_id,
            item_id=data.item_id
        )

        if existing_item:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This internal item is already mapped "
                    "to this platform connection"
                )
            )

        # -----------------------------------------------------
        # CHECK PLATFORM ITEM DUPLICATE
        # -----------------------------------------------------

        existing_platform_item = (
            await self.get_by_connection_and_platform_item(
                connection_id=data.online_platform_connection_id,
                platform_item_id=data.platform_item_id
            )
        )

        if existing_platform_item:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This platform item is already mapped "
                    "to an internal item"
                )
            )

        # -----------------------------------------------------
        # CREATE
        # -----------------------------------------------------

        mapping = OnlinePlatformItemMapping(
            online_platform_connection_id=(
                data.online_platform_connection_id
            ),
            item_id=data.item_id,
            platform_item_id=data.platform_item_id,
            platform_item_name=data.platform_item_name,
            is_active=data.is_active,
            notes=data.notes,
        )

        self.db.add(mapping)

        try:

            await self.db.commit()

        except IntegrityError:

            await self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item mapping already exists"
            )

        await self.db.refresh(mapping)

        return mapping

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    async def update(
        self,
        mapping_id: int,
        data: OnlinePlatformItemMappingUpdate
    ):

        mapping = await self.get_by_id(mapping_id)

        # -----------------------------------------------------
        # UPDATE ITEM
        # -----------------------------------------------------

        if data.item_id is not None:

            item_result = await self.db.execute(
                select(Item)
                .where(
                    Item.id == data.item_id
                )
            )

            item = item_result.scalar_one_or_none()

            if not item:

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Internal item not found"
                )

            # Get connection
            connection_result = await self.db.execute(
                select(OnlinePlatformConnection)
                .where(
                    OnlinePlatformConnection.id
                    == mapping.online_platform_connection_id
                )
            )

            connection = connection_result.scalar_one_or_none()

            if not connection:

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Online platform connection not found"
                )

            if item.branch_id != connection.branch_id:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Internal item does not belong to "
                        "the branch of this platform connection"
                    )
                )

            # Check duplicate
            if data.item_id != mapping.item_id:

                existing = (
                    await self.get_by_connection_and_item(
                        connection_id=(
                            mapping.online_platform_connection_id
                        ),
                        item_id=data.item_id
                    )
                )

                if existing and existing.id != mapping.id:

                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "This internal item is already "
                            "mapped to this connection"
                        )
                    )

            mapping.item_id = data.item_id

        # -----------------------------------------------------
        # UPDATE PLATFORM ITEM ID
        # -----------------------------------------------------

        if data.platform_item_id is not None:

            if data.platform_item_id != mapping.platform_item_id:

                existing = (
                    await self.get_by_connection_and_platform_item(
                        connection_id=(
                            mapping.online_platform_connection_id
                        ),
                        platform_item_id=data.platform_item_id
                    )
                )

                if existing and existing.id != mapping.id:

                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "This platform item ID is already "
                            "mapped to another item"
                        )
                    )

            mapping.platform_item_id = data.platform_item_id

        # -----------------------------------------------------
        # OTHER FIELDS
        # -----------------------------------------------------

        if data.platform_item_name is not None:
            mapping.platform_item_name = data.platform_item_name

        if data.is_active is not None:
            mapping.is_active = data.is_active

        if data.notes is not None:
            mapping.notes = data.notes

        try:

            await self.db.commit()

        except IntegrityError:

            await self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item mapping already exists"
            )

        await self.db.refresh(mapping)

        return mapping

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------

    async def list(
        self,
        connection_id: Optional[int] = None,
        item_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ):

        query = select(OnlinePlatformItemMapping)

        count_query = select(
            func.count(OnlinePlatformItemMapping.id)
        )

        # -----------------------------------------------------
        # FILTERS
        # -----------------------------------------------------

        if connection_id is not None:

            query = query.where(
                OnlinePlatformItemMapping
                .online_platform_connection_id
                == connection_id
            )

            count_query = count_query.where(
                OnlinePlatformItemMapping
                .online_platform_connection_id
                == connection_id
            )

        if item_id is not None:

            query = query.where(
                OnlinePlatformItemMapping.item_id
                == item_id
            )

            count_query = count_query.where(
                OnlinePlatformItemMapping.item_id
                == item_id
            )

        if is_active is not None:

            query = query.where(
                OnlinePlatformItemMapping.is_active
                == is_active
            )

            count_query = count_query.where(
                OnlinePlatformItemMapping.is_active
                == is_active
            )

        # -----------------------------------------------------
        # EXECUTE
        # -----------------------------------------------------

        query = query.order_by(
            OnlinePlatformItemMapping.id.desc()
        )

        result = await self.db.execute(query)

        mappings = result.scalars().all()

        count_result = await self.db.execute(
            count_query
        )

        total = count_result.scalar() or 0

        return mappings, total

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    async def delete(
        self,
        mapping_id: int
    ):

        mapping = await self.get_by_id(mapping_id)

        await self.db.delete(mapping)

        await self.db.commit()

        return {
            "message": "Item mapping deleted successfully"
        }

    # ---------------------------------------------------------
    # RESOLVE PLATFORM ITEM
    # ---------------------------------------------------------

    async def resolve_platform_item(
        self,
        connection_id: int,
        platform_item_id: str
    ):

        mapping = await self.get_by_connection_and_platform_item(
            connection_id=connection_id,
            platform_item_id=platform_item_id
        )

        if not mapping:

            return None

        if not mapping.is_active:

            return None

        return mapping