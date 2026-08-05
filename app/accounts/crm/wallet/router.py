"""
app/accounts/crm/wallet/router.py

FastAPI router for Customer Wallet.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from app.db.config import SessionDep
from app.accounts.crm.wallet.schema import WalletAccountOut, WalletTransactionOut
from app.accounts.crm.wallet import service

router = APIRouter(
    prefix="/crm/wallet",
    tags=["CRM Wallet"]
)


@router.get("/account", response_model=Optional[WalletAccountOut])
async def get_account(customer_id: int, db: SessionDep):
    account = await service.get_wallet_account(db, customer_id)
    if not account:
        raise HTTPException(404, "Wallet account not found")
    return account


@router.get("/transactions", response_model=List[WalletTransactionOut])
async def list_transactions(customer_id: int, db: SessionDep):
    return await service.get_wallet_transactions(db, customer_id)
