# # # """
# # # app/accounts/uploads/router.py
# # # Menu Bulk Upload Router — Production Ready
# # # """

# # # from fastapi import APIRouter, Depends, File, UploadFile
# # # from sqlalchemy.ext.asyncio import AsyncSession

# # # from app.db.config import get_db
# # # from app.accounts.deps import get_current_user  # adjust import to your auth module
# # # from app.accounts.uploads.service import BulkUploadService, MenuService

# # # router = APIRouter(
# # #     prefix="/bulk-uploads",
# # #     tags=["Uploads"],
# # # )


# # # @router.post("/bulk-upload")
# # # async def bulk_upload_menu(
# # #     file: UploadFile = File(...),
# # #     db: AsyncSession = Depends(get_db),
# # #     current_user=Depends(get_current_user),
# # # ):
# # #     client = current_user["user"]

# # #     return await MenuService.bulk_upload_menu(
# # #         db=db,
# # #         file=file,
# # #         client_id=client.id,
# # #     )


# # # @router.get("/template")
# # # async def download_template(
    
# # #     current_user=Depends(get_current_user),
# # #     module: str = "menu"
# # # ):
# # #     """
# # #     Download the Excel template for bulk upload.

# # #     Query param:
# # #       module — one of: menu (default: menu)
# # #     """
# # #     return await BulkUploadService.download_template(module)



# # """
# # app/accounts/uploads/router.py
# # Generic Bulk Upload Router — Production Ready
# # """

# # from fastapi import APIRouter, Depends, File, Query, UploadFile
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.db.config import get_db
# # from app.accounts.deps import get_current_user
# # from app.accounts.uploads.service import BulkUploadService, UPLOAD_CONFIG, TEMPLATES

# # router = APIRouter(prefix="/bulk-uploads", tags=["Uploads"])


# # @router.post("/upload")
# # async def bulk_upload(
# #     module: str = Query(..., description=f"Module to upload. One of: {list(UPLOAD_CONFIG)}"),
# #     file: UploadFile = File(...),
# #     db: AsyncSession = Depends(get_db),
# #     current_user=Depends(get_current_user),
# # ):
# #     """
# #     Generic bulk upload endpoint.
# #     Pass `module=menu`, `module=inventory`, `module=category`, etc.
# #     Upload the matching Excel template filled with your data.
# #     """
# #     client = current_user["user"]
# #     return await BulkUploadService.upload(
# #         db=db,
# #         file=file,
# #         module=module,
# #         client_id=client.id,
# #     )


# # @router.get("/template")
# # async def download_template(
# #     module: str = Query("menu", description=f"Module template to download. One of: {list(TEMPLATES)}"),
# #     current_user=Depends(get_current_user),
# # ):
# #     """
# #     Download the Excel template for any supported module.
# #     Query param: module — e.g. menu, inventory, category
# #     """
# #     return await BulkUploadService.download_template(module)


# # @router.get("/modules")
# # async def list_modules(current_user=Depends(get_current_user)):
# #     """Return all registered upload modules and their required sheets/columns."""
# #     from app.accounts.uploads.service import UPLOAD_CONFIG
# #     return {
# #         module: {
# #             "sheets": [
# #                 {"name": s.name, "required_columns": s.required_columns}
# #                 for s in config.sheets
# #             ]
# #         }
# #         for module, config in UPLOAD_CONFIG.items()
# #     }



# """
# app/accounts/uploads/router.py
# Generic Bulk Upload + Export Router — Production Ready
# """

# from fastapi import APIRouter, Depends, File, Query, UploadFile
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.db.config import get_db
# from app.accounts.deps import get_current_user
# from app.accounts.uploads.service import (
#     BulkUploadService,
#     BulkExportService,
#     UPLOAD_CONFIG,
#     TEMPLATES,
#     EXPORT_HANDLERS,
# )

# router = APIRouter(prefix="/bulk-uploads", tags=["Uploads"])


# @router.post("/upload")
# async def bulk_upload(
#     module: str = Query(..., description=f"Module to upload. One of: {list(UPLOAD_CONFIG)}"),
#     file: UploadFile = File(...),
#     db: AsyncSession = Depends(get_db),
#     current_user=Depends(get_current_user),
# ):
#     """
#     Generic bulk upload endpoint.
#     Pass `module=menu`, `module=inventory`, `module=category`, etc.
#     Upload the matching Excel template filled with your data.
#     """
#     client = current_user["user"]
#     return await BulkUploadService.upload(
#         db=db,
#         file=file,
#         module=module,
#         client_id=client.id,
#     )


# @router.get("/export")
# async def bulk_export(
#     module: str = Query(..., description=f"Module to export. One of: {list(EXPORT_HANDLERS)}"),
#     db: AsyncSession = Depends(get_db),
#     current_user=Depends(get_current_user),
# ):
#     """
#     Generic bulk export endpoint.

#     Returns a downloadable .xlsx file for the requested module.
#     Branch access is enforced automatically from the authenticated user:
#       - all_branches=True  → exports all branches owned by the client.
#       - all_branches=False → exports only the client's assigned branches.

#     Examples:
#       GET /bulk-uploads/export?module=menu
#       GET /bulk-uploads/export?module=inventory
#       GET /bulk-uploads/export?module=category
#     """
#     client = current_user["user"]
#     return await BulkExportService.export(
#         db=db,
#         module=module,
#         client=client,
#     )


# @router.get("/template")
# async def download_template(
#     module: str = Query("menu", description=f"Module template to download. One of: {list(TEMPLATES)}"),
#     current_user=Depends(get_current_user),
# ):
#     """
#     Download the Excel template for any supported module.
#     Query param: module — e.g. menu, inventory, category
#     """
#     return await BulkUploadService.download_template(module)


# @router.get("/modules")
# async def list_modules(current_user=Depends(get_current_user)):
#     """Return all registered upload modules and their required sheets/columns."""
#     return {
#         module: {
#             "sheets": [
#                 {"name": s.name, "required_columns": s.required_columns}
#                 for s in config.sheets
#             ]
#         }
#         for module, config in UPLOAD_CONFIG.items()
#     }




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

