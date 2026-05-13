from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.accounts.customer.model import Customer
from app.accounts.customer.schema import CustomerCreate, CustomerOut, CustomerUpdate
from app.db.config import SessionDep

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
async def get_customers(db: SessionDep):

    result = await db.execute(select(Customer))
    return result.scalars().all()



@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: int, db: SessionDep):

    customer = await db.get(Customer, customer_id)

    if not customer:
        raise HTTPException(404, "Customer not found")

    return customer



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

