# app/accounts/table/service.py

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.accounts.table.model import Table, TableStatus
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.order.model import Order, OrderItem
from app.accounts.deps import UserRole


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
        role,
        user
    ):
        query = await TableService.build_table_query(
            role,
            user
        )

        query = query.where(
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
        filter_status=None
    ):
        query = await TableService.build_table_query(
            role,
            user
        )

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

        result = await db.execute(query)

        tables = result.scalars().unique().all()

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

        return table

    @staticmethod
    async def delete_table(
        db,
        table
    ):
        await db.delete(table)
        await db.commit()

        return {
            "success": True,
            "message": "Table deleted successfully"
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

        return {
            "message": "Customer seated"
        }

    @staticmethod
    async def vacate_table(db, table):
        table.status = "available"

        await db.commit()

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

        await db.commit()
        await db.refresh(table)

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
                Table.branch_id.in_(branch_ids)
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
                    }
                    for t in branch_tables
                ]
            })

        return response