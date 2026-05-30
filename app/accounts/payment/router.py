from fastapi import (
    APIRouter,
    HTTPException
)

from sqlalchemy import select

from app.db.config import SessionDep

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus

from app.accounts.payment.model import Payment

from app.accounts.payment.schema import (
    PaymentCreate,
    PaymentOut
)


router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)


@router.post(
    "/pay",
    response_model=PaymentOut
)
async def make_payment(
    data: PaymentCreate,
    db: SessionDep
):

    # =====================================
    # BILL
    # =====================================

    result = await db.execute(
        select(Bill)
        .where(
            Bill.id == data.bill_id
        )
    )

    bill = result.scalar_one_or_none()

    if not bill:

        raise HTTPException(
            status_code=404,
            detail="Bill not found"
        )

    # =====================================
    # ALREADY PAID
    # =====================================

    if bill.payment_status == PaymentStatus.complete:

        raise HTTPException(
            status_code=400,
            detail="Bill already paid"
        )

    # =====================================
    # VALIDATION
    # =====================================

    if data.receive_amount < bill.due_amount:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Amount should be at least "
                f"{bill.due_amount}"
            )
        )

    # =====================================
    # CHANGE
    # =====================================

    change_amount = round(
        data.receive_amount -
        bill.due_amount,
        2
    )

    # =====================================
    # PAYMENT ENTRY
    # =====================================

    payment = Payment(

        bill_id=bill.id,

        order_id=bill.order_id,

        branch_id=bill.branch_id,

        payment_method=data.payment_method,

        bill_amount=bill.grand_total,

        receive_amount=data.receive_amount,

        paid_amount=bill.due_amount,

        change_amount=change_amount,

        payment_reference=(
            data.payment_reference
        ),

        notes=data.notes
    )

    db.add(payment)

    # =====================================
    # UPDATE BILL
    # =====================================

    bill.paid_amount = bill.grand_total

    bill.due_amount = 0

    bill.payment_status = (
        PaymentStatus.complete
    )

    bill.payment_method = (
        data.payment_method
    )

    await db.commit()

    await db.refresh(payment)

    return payment