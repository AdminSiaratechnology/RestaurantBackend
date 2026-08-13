from io import BytesIO
from urllib.parse import quote, unquote, urlparse

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.settings import settings


# ============================================================
# VALIDATE AWS CONFIGURATION
# ============================================================

if not settings.AWS_ACCESS_KEY_ID:
    raise RuntimeError("AWS_ACCESS_KEY_ID is missing from .env")

if not settings.AWS_SECRET_ACCESS_KEY:
    raise RuntimeError("AWS_SECRET_ACCESS_KEY is missing from .env")

if not settings.AWS_REGION:
    raise RuntimeError("AWS_REGION is missing from .env")

if not settings.AWS_S3_BUCKET:
    raise RuntimeError("AWS_S3_BUCKET is missing from .env")


# ============================================================
# S3 CLIENT
# ============================================================

s3_client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024


# ============================================================
# CREATE S3 URL
# ============================================================

def get_s3_url(object_key: str) -> str:

    encoded_key = quote(object_key, safe="/")

    return (
        f"https://{settings.AWS_S3_BUCKET}.s3."
        f"{settings.AWS_REGION}.amazonaws.com/"
        f"{encoded_key}"
    )


# ============================================================
# TEST S3 CONNECTION
# ============================================================

async def test_s3_connection():

    try:

        await run_in_threadpool(
            s3_client.head_bucket,
            Bucket=settings.AWS_S3_BUCKET,
        )

        print("S3 connection healthy.")

    except ClientError as exc:

        error = exc.response.get("Error", {})

        print("========== S3 CONNECTION ERROR ==========")
        print("Code   :", error.get("Code"))
        print("Message:", error.get("Message"))
        print("=========================================")

        raise RuntimeError(
            f"S3 connection failed: "
            f"{error.get('Code')} - {error.get('Message')}"
        ) from exc


# ============================================================
# UPLOAD IMAGE
# ============================================================

async def upload_file_to_s3(
    file: UploadFile,
    object_key: str,
) -> str:

    # --------------------------------------------------------
    # Validate content type
    # --------------------------------------------------------

    if file.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid image type. "
                "Only JPG, JPEG, PNG and WEBP images are allowed."
            ),
        )

    # --------------------------------------------------------
    # Read file
    # --------------------------------------------------------

    file_data = await file.read()

    if not file_data:

        raise HTTPException(
            status_code=400,
            detail="Empty image file",
        )

    # --------------------------------------------------------
    # Validate size
    # --------------------------------------------------------

    if len(file_data) > MAX_IMAGE_SIZE:

        raise HTTPException(
            status_code=400,
            detail="Image size cannot exceed 5 MB",
        )

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    try:

        await run_in_threadpool(
            s3_client.put_object,
            Bucket=settings.AWS_S3_BUCKET,
            Key=object_key,
            Body=BytesIO(file_data),
            ContentType=file.content_type,
        )

    except ClientError as exc:

        error = exc.response.get("Error", {})

        print("========== S3 UPLOAD ERROR ==========")
        print("Bucket :", settings.AWS_S3_BUCKET)
        print("Region :", settings.AWS_REGION)
        print("Key    :", object_key)
        print("Code   :", error.get("Code"))
        print("Message:", error.get("Message"))
        print("Full   :", exc)
        print("=====================================")

        raise HTTPException(
            status_code=500,
            detail=(
                f"S3 upload failed: "
                f"{error.get('Code')} - "
                f"{error.get('Message')}"
            ),
        ) from exc

    except BotoCoreError as exc:

        print("========== S3 BOTO ERROR ==========")
        print(exc)
        print("===================================")

        raise HTTPException(
            status_code=500,
            detail="AWS S3 client error",
        ) from exc

    # --------------------------------------------------------
    # Return URL
    # --------------------------------------------------------

    return get_s3_url(object_key)


# ============================================================
# DELETE IMAGE
# ============================================================

async def delete_file_from_s3(
    object_key: str,
):

    if not object_key:
        return

    try:

        await run_in_threadpool(
            s3_client.delete_object,
            Bucket=settings.AWS_S3_BUCKET,
            Key=object_key,
        )

    except ClientError as exc:

        error = exc.response.get("Error", {})

        print("========== S3 DELETE ERROR ==========")
        print("Code   :", error.get("Code"))
        print("Message:", error.get("Message"))
        print("Full   :", exc)
        print("=====================================")

        raise HTTPException(
            status_code=500,
            detail=(
                f"S3 delete failed: "
                f"{error.get('Code')} - "
                f"{error.get('Message')}"
            ),
        ) from exc


# ============================================================
# EXTRACT OBJECT KEY FROM URL
# ============================================================

def get_s3_object_key(
    image_url: str | None,
) -> str | None:

    if not image_url:
        return None

    base_url = (
        f"https://{settings.AWS_S3_BUCKET}.s3."
        f"{settings.AWS_REGION}.amazonaws.com/"
    )

    if image_url.startswith(base_url):
        return unquote(image_url[len(base_url):])

    parsed = urlparse(image_url)
    if parsed.path:
        key = parsed.path.lstrip('/')
        return unquote(key) if key else None

    return None