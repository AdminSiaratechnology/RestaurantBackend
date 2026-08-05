"""
app/accounts/crm/example_bill_integration.py

Production-ready example illustrating integration of CRM Event Publishing 
into a FastAPI Bill Creation endpoint.

Flow:
1. Create Order & Bill in Postgres.
2. Commit DB transaction.
3. Publish `bill_completed` event to Redis.
4. Immediately return HTTP 200/201 response to client.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.config import get_db
from app.accounts.bill.model import Bill
from app.accounts.crm.events.publisher import crm_event_publisher
from app.accounts.crm.utils.logger import crm_logger

router = APIRouter(prefix="/api/v1/bills", tags=["Billing & Payments"])


class BillCreateSchema(BaseModel):
    order_id: int
    customer_id: int
    client_id: int
    branch_id: int
    grand_total: float
    payment_method: str = "UPI"


class BillResponseSchema(BaseModel):
    status: str
    message: str
    bill_id: int
    invoice_no: str
    grand_total: float


@router.post("/create", response_model=BillResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_bill(
    payload: BillCreateSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Bill for Completed Order.
    
    API guarantees:
    - Zero delay for CRM processing.
    - CRM event is published to Redis asynchronously after DB transaction commit.
    """
    # 1. Generate Invoice Number & Bill Model
    invoice_no = f"INV-{payload.client_id}-{payload.branch_id}-{payload.order_id}"
    
    new_bill = Bill(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        client_id=payload.client_id,
        branch_id=payload.branch_id,
        invoice_no=invoice_no,
        order_type="Dine-In",
        payment_method=payload.payment_method,
        grand_total=payload.grand_total,
        final_amount=payload.grand_total
    )

    # 2. Add and Commit Database Transaction
    db.add(new_bill)
    await db.commit()
    await db.refresh(new_bill)

    # 3. Publish Event to Redis (Non-blocking async call)
    # Using FastAPI BackgroundTasks or direct await (both are <2ms)
    async def _publish():
        await crm_event_publisher.publish_bill_completed(
            bill_id=new_bill.id,
            order_id=new_bill.order_id,
            customer_id=new_bill.customer_id,
            client_id=new_bill.client_id,
            branch_id=new_bill.branch_id
        )

    background_tasks.add_task(_publish)

    # 4. Return Immediate Response to Client
    return BillResponseSchema(
        status="success",
        message="Bill generated successfully. CRM processing queued asynchronously.",
        bill_id=new_bill.id,
        invoice_no=new_bill.invoice_no,
        grand_total=new_bill.grand_total
    )
