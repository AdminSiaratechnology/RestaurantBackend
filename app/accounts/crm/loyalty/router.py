"""
app/accounts/crm/loyalty/router.py

FastAPI router for Customer Loyalty.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.db.config import SessionDep
from app.accounts.crm.loyalty.schema import LoyaltyAccountOut, LoyaltyTransactionOut
from app.accounts.crm.loyalty import service

router = APIRouter(
    prefix="/crm/loyalty",
    tags=["CRM Loyalty"]
)


@router.get("/account", response_model=Optional[LoyaltyAccountOut])
async def get_account(customer_id: int, db: SessionDep):
    account = await service.get_loyalty_account(db, customer_id)
    if not account:
        raise HTTPException(404, "Loyalty account not found")
    return account


@router.get("/transactions", response_model=List[LoyaltyTransactionOut])
async def list_transactions(customer_id: int, db: SessionDep):
    return await service.get_loyalty_transactions(db, customer_id)
