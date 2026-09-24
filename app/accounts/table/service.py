# app/accounts/table/service.py

from app.accounts.bill.enum import PaymentStatus
from app.accounts.bill.model import Bill
from fastapi import HTTPException
from sqlalchemy import select, distinct
from sqlalchemy.orm import selectinload
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.order.model import Order, OrderItem
from app.accounts.deps import UserRole
from app.core.cache import Cache
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.accounts.table.model import Table
from app.accounts.table.enum import TableStatus

from app.accounts.order.model import Order, OrderItem
from app.accounts.item.model import Item


class TableService:

    @staticmethod
    async def create_table(db, data, user):
        result = await db.execute(
            select(Branch).where(
                Branch.id == data.branch_id
            )
        )

        branch = result.scalar_one_or_none()

        if not branch:
            raise HTTPException(404, "Branch not found")

        if branch.client_id != user.id:
            raise HTTPException(403, "Not allowed")

        table = Table(
            client_id=branch.client_id,
            branch_id=branch.id,
            name=data.name,
            floor=data.floor,
            number_of_seats=data.number_of_seats,
            shape=data.shape
        )

        db.add(table)
        await db.commit()
        await db.refresh(table)

        await Cache.delete(f"tables:branch:{table.branch_id}")

        return table

    @staticmethod
    async def build_table_query(role, user):
        query = (
            select(Table)
            .join(Branch, Branch.id == Table.branch_id)
        )

        if role == UserRole.SUPER_ADMIN:
            pass

        elif role == UserRole.PARTNER:
            query = (
                query
                .join(Client, Client.id == Branch.client_id)
                .where(Client.partner_id == user.id)
            )

        elif role == UserRole.CLIENT:
            query = query.where(
                Branch.client_id == user.id
            )

        elif role == UserRole.STAFF:
            query = query.where(
                Table.branch_id == user.branch_id
            )

        else:
            raise HTTPException(403, "Not authorized")

        return query

    @staticmethod
    async def get_table_by_id(
        db,
        table_id,
        role=None,
        user=None
    ):
        if role is not None and user is not None:
            query = await TableService.build_table_query(
                role,
                user
            )
            query = query.where(
                Table.id == table_id
            )
        else:
            query = select(Table).where(
                Table.id == table_id
            )

        result = await db.execute(query)

        table = result.scalar_one_or_none()

        if not table:
            raise HTTPException(
                404,
                "Table not found"
            )

        return table

    @staticmethod
    async def get_tables(
        db,
        role,
        user,
        branch_id=None,
        filter_status=None,
        include_inactive: bool = False
    ):
        query = await TableService.build_table_query(
            role,
            user
        )

        if not include_inactive:
            query = query.where(Table.is_active == True)

        if branch_id:
            query = query.where(
                Table.branch_id == branch_id
            )

            if (
                role == UserRole.STAFF
                and branch_id != user.branch_id
            ):
                raise HTTPException(
                    403,
                    "Not allowed to access this branch"
                )

            cache_key = f"tables:branch:{branch_id}"
            cached_tables = await Cache.get(cache_key)
            if cached_tables:
                if not include_inactive:
                    cached_tables = [t for t in cached_tables if t.get("is_active") is not False]
                if filter_status:
                    return [t for t in cached_tables if t.get("status") == filter_status]
                return cached_tables

        result = await db.execute(query)

        tables = result.scalars().unique().all()

        if branch_id:
            await Cache.set(f"tables:branch:{branch_id}", jsonable_encoder(tables), expire=1800)

        if filter_status:
            tables = [
                t for t in tables
                if t.status == filter_status
            ]

        return tables

    @staticmethod
    async def update_table(
        db,
        table,
        data
    ):
        update_data = data.model_dump(
            exclude_unset=True
        )

        for key, value in update_data.items():
            setattr(table, key, value)

        await db.commit()
        await db.refresh(table)

        await Cache.delete(f"tables:branch:{table.branch_id}")

        return table

    @staticmethod
    async def delete_table(db, table):
        branch_id = table.branch_id

    # Check whether this table has ever been used
        order = await db.scalar(
            select(Order).where(Order.table_id == table.id).limit(1)
        )

        if order:
        # Soft delete
            table.is_active = False
            await db.commit()
            await db.refresh(table)

            await Cache.delete(f"tables:branch:{branch_id}")

            return {
                "success": True,
                "message": "Table has order history, so it was deactivated instead of deleted."
            }

    # Never used -> permanently delete
        await db.delete(table)
        await db.commit()

        await Cache.delete(f"tables:branch:{branch_id}")

        return {
            "success": True,
            "message": "Table deleted successfully."
        }

    @staticmethod
    async def seat_table(db, table):
        if table.status != "available":
            raise HTTPException(
                400,
                "Table not available"
            )

        table.status = "occupied"

        await db.commit()
        
        await Cache.delete(f"tables:branch:{table.branch_id}")

        return {
            "message": "Customer seated"
        }

    @staticmethod
    async def vacate_table(db, table):
        table.status = "available"

        await db.commit()

        await Cache.delete(f"tables:branch:{table.branch_id}")

        return {
            "message": "Table vacated"
        }

    @staticmethod
    async def update_status(
        db,
        table,
        status
    ):
        table.status = status

        status_val = status.value if hasattr(status, "value") else str(status)
        if status_val == "available":
            from app.accounts.table_qr.model import RestaurantSession, SessionStatus
            from sqlalchemy import update
            await db.execute(
                update(RestaurantSession)
                .where(
                    RestaurantSession.table_id == table.id,
                    RestaurantSession.status == SessionStatus.ACTIVE.value,
                )
                .values(status=SessionStatus.COMPLETED.value)
            )

        await db.commit()
        await db.refresh(table)
        
        await Cache.delete(f"tables:branch:{table.branch_id}")

        return table

    @staticmethod
    async def get_table_orders(
        db,
        table_id
    ):
        order_result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.order_items)
                .selectinload(OrderItem.item)
            )
            .where(
                Order.table_id == table_id,
                Order.status.notin_(
                    ["completed", "paid", "cancelled"]
                )
            )
            .order_by(
                Order.created_at.desc()
            )
        )

        return order_result.scalars().first()
    
    @staticmethod
    async def table_dashboard_all_branches(
        db,
        client_id: int
    ):
        branches_result = await db.execute(
            select(Branch).where(
                Branch.client_id == client_id
            )
        )

        branches = branches_result.scalars().all()

        branch_ids = [b.id for b in branches]

        if not branch_ids:
            return {
                "total_tables": 0,
                "available": 0,
                "occupied": 0,
                "reserved": 0,
                "branches": []
            }

        tables_result = await db.execute(
            select(Table).where(
                Table.branch_id.in_(branch_ids),
                Table.is_active == True
            )
        )

        tables = tables_result.scalars().all()

        response = {
            "total_tables": len(tables),
            "available": 0,
            "occupied": 0,
            "reserved": 0,
            "branches": []
        }

        for table in tables:
            if str(table.status) == "available":
                response["available"] += 1
            elif str(table.status) == "occupied":
                response["occupied"] += 1
            elif str(table.status) == "reserved":
                response["reserved"] += 1

        for branch in branches:
            branch_tables = [
                t for t in tables
                if t.branch_id == branch.id
            ]

            response["branches"].append({
                "branch_id": branch.id,
                "branch_name": branch.name,
                "total_tables": len(branch_tables),
                "tables": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "floor": t.floor,
                        "number_of_seats": t.number_of_seats,
                        "shape": t.shape.value if hasattr(t.shape, "value") else t.shape,
                        "status": t.status.value if hasattr(t.status, "value") else t.status,
                        "is_active": t.is_active,
                    }
                    for t in branch_tables
                ]
            })

        return response

    @staticmethod
    async def get_table_details(
        db,
        table_id,
        role,
        user
    ):
        table = await TableService.get_table_by_id(
            db,
            table_id,
            role,
            user
        )

        if table.status != TableStatus.occupied:
            return {
                "table_id": table.id,
                "table_name": table.name,
                "status": table.status.value if hasattr(table.status, "value") else table.status,
                "customer_name": None,
                "order_id": None,
                "total_amount": 0.0,
                "items": []
            }

        result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.order_items)
                .selectinload(OrderItem.item)
            )
            .where(
                Order.table_id == table.id,
                Order.status.notin_(
                    ["completed", "paid", "cancelled"]
                )
            )
            .order_by(Order.created_at.desc())
        )

        order = result.scalars().first()

        if not order:
            return {
                "table_id": table.id,
                "table_name": table.name,
                "status": table.status.value,
                "customer_name": None,
                "order_id": None,
                "total_amount": 0,
                "items": []
            }

        return {
            "table_id": table.id,
            "table_name": table.name,
            "status": table.status.value,
            "customer_name": order.customer_name,
            "order_id": order.id,
            "total_amount": order.total_amount,
            "items": [
                {
                    "order_item_id": item.id,
                    "item_id": item.item.id,
                    "item_name": item.item.name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "subtotal": item.total_price,
                    "order_status": item.order_status
                }
                for item in order.order_items
            ]
        }
    


    @staticmethod
    async def get_table_availability(db, table_id: int):

        result = await db.execute(
            select(Table)
            .where(Table.id == table_id)
        )

        table = result.scalar_one_or_none()

        if not table:
            raise HTTPException(404, "Table not found")

        order_result = await db.execute(
            select(Order)
            .where(
                Order.table_id == table.id,
                Order.status.notin_(["completed", "cancelled"])
            )
            .order_by(Order.created_at.desc())
        )

        order = order_result.scalar_one_or_none()

        if not order:
            return {
                "table_id": table.id,
                "status": "available",
                "available": True
            }

        bill_result = await db.execute(
            select(Bill)
            .where(Bill.order_id == order.id)
        )

        bill = bill_result.scalar_one_or_none()

        if bill and bill.payment_status == PaymentStatus.complete:
            return {
                "table_id": table.id,
                "status": "available",
                "available": True
            }

        return {
            "table_id": table.id,
            "status": "occupied",
            "available": False,
            "order_id": order.id,
            "payment_status": bill.payment_status if bill else "pending"
        }

    @staticmethod
    async def update_layout(
        db,
        table,
        data,
    ):
        """
        Persist canvas layout position for a table.
        Only updates fields that are explicitly provided (not None).
        Does NOT touch status, orders, billing, QR, or any business logic.
        """
        if data.pos_x is not None:
            table.pos_x = data.pos_x
        if data.pos_y is not None:
            table.pos_y = data.pos_y
        if data.rotation is not None:
            table.rotation = data.rotation
        if data.layout_width is not None:
            table.layout_width = data.layout_width
        if data.layout_height is not None:
            table.layout_height = data.layout_height

        await db.commit()
        await db.refresh(table)

        # Invalidate the branch table cache so the next list request
        # returns fresh position data.
        await Cache.delete(f"tables:branch:{table.branch_id}")

        return table

    @staticmethod
    async def update_floor(
        db,
        table,
        data,
    ):
        """
        Atomically update table floor assignment and position (pos_x, pos_y).
        Does NOT alter active orders, bills, QR codes, sessions, or table ID.
        """
        if data.floor:
            table.floor = data.floor.strip()
        if data.pos_x is not None:
            table.pos_x = data.pos_x
        if data.pos_y is not None:
            table.pos_y = data.pos_y

        await db.commit()
        await db.refresh(table)

        await Cache.delete(f"tables:branch:{table.branch_id}")

        return table

    @staticmethod
    async def get_floors(
        db,
        role,
        user,
        branch_id: int | None = None,
    ) -> list[str]:
        """
        Returns the unique set of floor names for a branch.
        Floors are derived from the Table.floor string field — no separate Floor model.
        Respects the same branch isolation as get_tables.
        """
        query = await TableService.build_table_query(role, user)

        if branch_id:
            # Validate staff branch access
            if role == UserRole.STAFF and branch_id != user.branch_id:
                raise HTTPException(403, "Not allowed to access this branch")
            query = query.where(Table.branch_id == branch_id)

        # SELECT DISTINCT floor FROM tables WHERE ...
        floors_query = (
            select(distinct(Table.floor))
            .select_from(query.subquery())
            .where(Table.floor.isnot(None))
            .where(Table.is_active == True)
        )

        result = await db.execute(floors_query)
        floors = [row[0] for row in result.fetchall() if row[0]]
        return sorted(floors)