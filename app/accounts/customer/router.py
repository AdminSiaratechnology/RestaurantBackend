from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.customer.model import Customer
from app.accounts.customer.schema import CustomerCreate, CustomerOut, CustomerUpdate
from app.db.config import SessionDep
from app.accounts.deps import access_one, UserRole

router = APIRouter(prefix="/customers", tags=["Customers"])



@router.post("/", response_model=CustomerOut)
async def create_customer(
    payload: CustomerCreate,
    db: SessionDep
):

    # ✅ Get branch
    branch = await db.get(
        Branch,
        payload.branch_id
    )

    if not branch:
        raise HTTPException(
            404,
            "Branch not found"
        )

    # ✅ Duplicate check
    result = await db.execute(
        select(Customer).where(
            Customer.phone == payload.phone,
            Customer.client_id == branch.client_id
        )
    )

    existing = result.scalar_one_or_none()

    if existing:
        return existing

    # ✅ Create customer
    customer = Customer(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,

        # 🔥 Auto fetched
        branch_id=branch.id,
        branch_name=branch.name,
        client_id=branch.client_id
    )

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

    elif role == UserRole.STAFF:

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
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: SessionDep
):

    customer = await db.get(Customer, customer_id)

    if not customer:
        raise HTTPException(404, "Customer not found")

    update_data = payload.dict(exclude_unset=True)

    # ✅ Handle branch update
    if "branch_id" in update_data:

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

    # ✅ Other fields
    for key, value in update_data.items():

        if key != "branch_id":
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

