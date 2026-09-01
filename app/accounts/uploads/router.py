
from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.config import get_db
from app.accounts.deps import get_current_user
from app.accounts.uploads.service import BulkUploadService, BulkExportService

router = APIRouter(
    prefix="/bulk-uploads",
    tags=["Uploads"],
)


@router.post("/upload")
async def bulk_upload(
    file: UploadFile = File(...),
    module: str = Query("menu"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    client = current_user["user"]  # raw Client or Staff model object
    return await BulkUploadService.upload(
        db=db,
        file=file,
        module=module,
        client_id=client.id,
    )


@router.get("/template")
async def download_template(
    module: str = "menu",
    current_user=Depends(get_current_user),
):
    return await BulkUploadService.download_template(module)


@router.get("/export")
async def export_data(
    module: str = Query("menu"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    client = current_user["user"]  # ← this is what get_allowed_branches receives
    return await BulkExportService.export(
        db=db,
        module=module,
        client=client,   # pass the model object directly, not the dict
    )

