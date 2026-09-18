from fastapi import APIRouter, Depends, HTTPException

from app.accounts.deps import access_four
from app.accounts.table_qr.schema import TableQROut
from app.accounts.table_qr.service import TableQRService
from app.db.config import SessionDep

router = APIRouter(
    prefix="/tables",
    tags=["Staff Table QR Management"],
)


@router.post(
    "/{table_id}/qr",
    response_model=TableQROut,
)
async def generate_table_qr(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four),
):
    return await TableQRService.generate_qr(
        db=db,
        table_id=table_id,
        user=current["user"],
        role=current["role"],
    )


@router.get(
    "/{table_id}/qr",
    response_model=TableQROut,
)
async def get_table_qr(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four),
):
    return await TableQRService.get_qr(
        db=db,
        table_id=table_id,
        user=current["user"],
        role=current["role"],
    )


@router.post(
    "/{table_id}/qr/regenerate",
    response_model=TableQROut,
)
async def regenerate_table_qr(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four),
):
    return await TableQRService.regenerate_qr(
        db=db,
        table_id=table_id,
        user=current["user"],
        role=current["role"],
    )


@router.post(
    "/{table_id}/qr/disable",
    response_model=TableQROut,
)
async def disable_table_qr(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four),
):
    return await TableQRService.disable_qr(
        db=db,
        table_id=table_id,
        user=current["user"],
        role=current["role"],
    )


from fastapi.responses import StreamingResponse

@router.get(
    "/{table_id}/qr/image",
)
async def get_table_qr_image(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four),
):
    buf = await TableQRService.get_qr_image(
        db=db,
        table_id=table_id,
        user=current["user"],
        role=current["role"],
    )
    return StreamingResponse(buf, media_type="image/png")
