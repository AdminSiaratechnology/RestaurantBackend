from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.client.model import Client
from app.accounts.customer.model import Customer
from app.accounts.customer.schema import CustomerCreate, CustomerOut, CustomerUpdate
from app.db.config import SessionDep
from app.accounts.deps import access_one, UserRole

router = APIRouter(prefix="/customers", tags=["Customers"])



@router.post("/", response_model=CustomerOut)
async def create_customer(payload: CustomerCreate, db: SessionDep):

    # 🔍 Check duplicate (phone per client)
    result = await db.execute(
        select(Customer).where(
            Customer.phone == payload.phone,
            Customer.client_id == payload.client_id
        )
    )
    existing = result.scalar_one_or_none()


    if existing:
        return existing

    customer = Customer(**payload.dict())

    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    return customer



@router.get("/", response_model=list[CustomerOut])
async def get_customers(
    db: SessionDep,
    current=Depends(access_one),
    client_id: int | None = None,
    branch_id: int | None = None
):

    role = current["role"]
    user = current["user"]

    query = select(Customer)

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:

        if client_id:
            query = query.where(Customer.client_id == client_id)

    # ✅ PARTNER
    elif role == UserRole.PARTNER:

        query = query.join(
            Client,
            Client.id == Customer.client_id
        ).where(
            Client.partner_id == user.id
        )

        if client_id:
            query = query.where(Customer.client_id == client_id)

    # ✅ CLIENT
    elif role == UserRole.CLIENT:

        query = query.where(
            Customer.client_id == user.id
        )

    else:
        raise HTTPException(403, "Access denied")

    # ✅ Optional branch filter
    if branch_id:
        query = query.where(
            Customer.branch_id == branch_id
        )

    result = await db.execute(query)

    return result.scalars().all()






@router.put("/{customer_id}", response_model=CustomerOut)
async def update_customer(customer_id: int, payload: CustomerUpdate, db: SessionDep):

    customer = await db.get(Customer, customer_id)

    if not customer:
        raise HTTPException(404, "Customer not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)

    return customer


# ✅ DELETE CUSTOMER
@router.delete("/{customer_id}")
async def delete_customer(customer_id: int, db: SessionDep):

    customer = await db.get(Customer, customer_id)

    if not customer:
        raise HTTPException(404, "Customer not found")

    await db.delete(customer)
    await db.commit()

    return {"message": "Customer deleted"}

