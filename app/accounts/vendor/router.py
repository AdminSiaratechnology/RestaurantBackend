from app.db.config import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.accounts.vendor.enum import PaymentMethod, VendorStatus, VendorType
from app.accounts.vendor.schema import (
    VendorCreate,
    VendorUpdate,
    VendorResponse
)

from app.accounts.vendor.service import VendorService

router = APIRouter(
    prefix="/vendors",
    tags=["Vendors"]
)


# @router.post(
#     "/create",
#     response_model=VendorResponse
# )
# def create_vendor(
#     payload: VendorCreate,
#     db: Session = Depends(get_db)
# ):
#     return VendorService.create_vendor(
#         db,
#         payload
#     )


@router.post("/create")
async def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db)
):
    return await VendorService.create_vendor(
        db,
        payload
    )



@router.get("/all")
async def get_all_vendors(
    db: Session = Depends(get_db)
):
    return await VendorService.get_all_vendors(db)


@router.get(
    "/{vendor_id}",
    response_model=VendorResponse
)
async def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db)
):
    vendor = VendorService.get_vendor(
        db,
        vendor_id
    )

    if not vendor:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found"
        )

    return vendor


@router.put(
    "/{vendor_id}",
    response_model=VendorResponse
)
async def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: Session = Depends(get_db)
):
    vendor = await VendorService.update_vendor(
        db,
        vendor_id,
        payload
    )

    if not vendor:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found"
        )

    return vendor


@router.delete("/{vendor_id}")
async def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db)
):
    success = await VendorService.delete_vendor(
        db,
        vendor_id
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found"
        )

    return {
        "message": "Vendor deleted successfully"
    }


@router.get("/search")
async def search_vendors(
    q: str,
    db: Session = Depends(get_db)
):
    return VendorService.search_vendors(
        db,
        q
    )