

from fastapi import APIRouter, Depends, HTTPException

from app.accounts.customer.schema import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate
)

from app.accounts.customer.service import (
    create_customer_service,
    get_customers_all_branches,
    get_customers_service,
    update_customer_service,
    delete_customer_service
)

from app.accounts.deps import (
    access_one,UserRole
)

from app.db.config import SessionDep

router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


@router.post(
    "/",
    response_model=CustomerOut
)
async def create_customer(
    payload: CustomerCreate,
    db: SessionDep
):
    return await create_customer_service(
        payload=payload,
        db=db
    )



@router.get(
    "/",
    response_model=list[CustomerOut]
)
async def get_customers(
    db: SessionDep,
    current=Depends(access_one),
    client_id: int | None = None,
    branch_id: int | None = None
):
    return await get_customers_service(
        db=db,
        current=current,
        client_id=client_id,
        branch_id=branch_id
    )


@router.put(
    "/{customer_id}",
    response_model=CustomerOut
)
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: SessionDep
):
    return await update_customer_service(
        customer_id=customer_id,
        payload=payload,
        db=db
    )



@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: SessionDep
):
    return await delete_customer_service(
        customer_id=customer_id,
        db=db
    )



@router.get("/dashboard/all-branches")
async def customers_all_branches(
    db: SessionDep,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    if role == UserRole.CLIENT:

        client_id = user.id

    elif role == UserRole.PARTNER:

        raise HTTPException(
            403,
            "Use partner-specific implementation"
        )

    else:
        raise HTTPException(
            403,
            "Access denied"
        )

    return await get_customers_all_branches(
        db=db,
        client_id=client_id
    )