from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select, desc
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.customer.model import Customer
from app.accounts.customer.schema import (
    CustomerCreate,
    CustomerUpdate
)
from app.accounts.deps import UserRole
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError


async def create_customer_service(
    payload: CustomerCreate,
    db
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
        select(Customer).where(
            Customer.phone == payload.phone,
            Customer.client_id == branch.client_id
        )
    )

    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Customer with phone '{payload.phone}' already exists "
                f"for this client (customer_id={existing.id}, "
                f"registered at branch_id={existing.branch_id})."
            )
        )

    customer = Customer(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        gender=payload.gender,
        dob=payload.dob,
        anniversary=payload.anniversary,
        customer_source=payload.customer_source,
        branch_id=branch.id,
        branch_name=branch.name,
        client_id=branch.client_id,
    )

    db.add(customer)

    await db.commit()
    await db.refresh(customer)

    return customer


async def get_customers_service(
    db,
    current,
    client_id=None,
    branch_id=None
):
    role = current["role"]
    user = current["user"]

    query = select(Customer)

    if role == UserRole.SUPER_ADMIN:

        if client_id:
            query = query.where(
                Customer.client_id == client_id
            )

    elif role == UserRole.PARTNER:

        query = (
            query.join(
                Client,
                Client.id == Customer.client_id
            )
            .where(
                Client.partner_id == user.id
            )
        )

        if client_id:
            query = query.where(
                Customer.client_id == client_id
            )

    elif role == UserRole.CLIENT:

        query = query.where(
            Customer.client_id == user.id
        )

    elif role == UserRole.STAFF:

        query = query.where(
            Customer.client_id == user.client_id
        )

    else:
        raise HTTPException(
            403,
            "Access denied"
        )

    if branch_id:
        query = query.where(
            Customer.branch_id == branch_id
        )

    query = query.order_by(
        desc(Customer.created_at)
    )

    result = await db.execute(query)

    return result.scalars().all()


async def update_customer_service(
    customer_id: int,
    payload: CustomerUpdate,
    db
):
    customer = await db.get(
        Customer,
        customer_id
    )

    if not customer:
        raise HTTPException(
            404,
            "Customer not found"
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if "phone" in update_data:
        result = await db.execute(
            select(Customer).where(
                Customer.phone == update_data["phone"],
                Customer.client_id == customer.client_id,
                Customer.id != customer.id
            )
        )

        duplicate = result.scalar_one_or_none()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Phone number already exists."
            )

    if "branch_id" in update_data:
        if update_data["branch_id"] != customer.branch_id:
            branch = await db.get(
                Branch,
                update_data["branch_id"]
            )

            if not branch:
                raise HTTPException(
                    404,
                    "Branch not found"
                )

            customer.branch_id = branch.id
            customer.branch_name = branch.name
            customer.client_id = branch.client_id

    for key, value in update_data.items():
        if key != "branch_id":
            setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)

    return customer


async def delete_customer_service(
    customer_id: int,
    db
):
    customer = await db.get(
        Customer,
        customer_id
    )

    if not customer:
        raise HTTPException(
            404,
            "Customer not found"
        )

    await db.delete(customer)
    await db.commit()

    return {
        "message": "Customer deleted"
    }


async def get_customers_all_branches(
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
            "total_customers": 0,
            "branches": []
        }

    customers_result = await db.execute(
        select(Customer).where(
            Customer.client_id == client_id
        )
    )

    customers = customers_result.scalars().all()

    response = {
        "total_customers": len(customers),
        "branches": []
    }

    for branch in branches:

        branch_customers = [
            c for c in customers
            if c.branch_id == branch.id
        ]

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_customers": len(branch_customers),

            "customers": [
                {
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone,
                    "email": c.email,
                    "address": c.address,
                    "created_at": c.created_at
                }
                for c in branch_customers
            ]
        })

    return response


async def find_existing_customer(
    db,
    client_id: int,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
):
    if phone:
        customer = await db.scalar(
            select(Customer).where(
                Customer.client_id == client_id,
                Customer.phone == phone,
            )
        )

        if customer:
            return customer

    if email:
        customer = await db.scalar(
            select(Customer).where(
                Customer.client_id == client_id,
                func.lower(Customer.email) == email.lower(),
            )
        )

        if customer:
            return customer

    if name and phone:
        customer = await db.scalar(
            select(Customer).where(
                Customer.client_id == client_id,
                func.lower(Customer.name) == name.lower(),
                Customer.phone == phone,
            )
        )

        if customer:
            return customer

    if name and email:
        customer = await db.scalar(
            select(Customer).where(
                Customer.client_id == client_id,
                func.lower(Customer.name) == name.lower(),
                func.lower(Customer.email) == email.lower(),
            )
        )

        if customer:
            return customer

    return None


async def create_customer_from_order(
    db,
    *,
    client_id: int,
    branch_id: int,
    branch_name: str,
    name: str,
    phone: str | None,
    email: str | None,
):
    customer = Customer(
        client_id=client_id,
        branch_id=branch_id,
        branch_name=branch_name,
        name=name or "Guest",
        phone=phone,
        email=email,
    )

    db.add(customer)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()

        customer = await find_existing_customer(
            db=db,
            client_id=client_id,
            name=name,
            phone=phone,
            email=email,
        )

        if customer:
            return customer

        raise

    await db.refresh(customer)

    return customer


async def find_or_create_customer(
    db,
    *,
    client_id: int,
    branch_id: int,
    branch_name: str,
    name: str,
    phone: str | None = None,
    email: str | None = None,
):
    phone = (phone.strip() if phone and phone.strip() else None)
    email = (email.strip() if email and email.strip() else None)
    name = (name.strip() if name and name.strip() else "Walk-in Guest")

    if not phone and not email:
        phone = f"GUEST-{client_id}-{branch_id}"
        name = name or "Walk-in Guest"

    if not phone and email:
        phone = f"GUEST-EMAIL-{client_id}-{branch_id}"

    customer = await find_existing_customer(
        db=db,
        client_id=client_id,
        name=name,
        phone=phone,
        email=email,
    )

    if customer:
        return customer, False

    customer = await create_customer_from_order(
        db=db,
        client_id=client_id,
        branch_id=branch_id,
        branch_name=branch_name,
        name=name,
        phone=phone,
        email=email,
    )

    return customer, True