"""
app/accounts/crm/tags/router.py

FastAPI router for Customer Tags.
"""

from typing import List
from fastapi import APIRouter
from app.db.config import SessionDep
from app.accounts.crm.tags.schema import CustomerTagCreate, CustomerTagOut
from app.accounts.crm.tags import service

router = APIRouter(
    prefix="/crm/tags",
    tags=["CRM Tags"]
)


@router.post("", response_model=CustomerTagOut)
async def create_tag(payload: CustomerTagCreate, db: SessionDep):
    return await service.create_tag(db, payload)


@router.get("", response_model=List[CustomerTagOut])
async def list_tags(customer_id: int, db: SessionDep):
    return await service.get_customer_tags(db, customer_id)
