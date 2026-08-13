
# import os
# from dotenv import load_dotenv
# from pathlib import Path

# # Load .env from project root
# BASE_DIR = Path(__file__).resolve().parent.parent.parent
# load_dotenv(BASE_DIR / ".env")


# class Settings:
#     # --------------------------------------------------
#     # Database
#     # --------------------------------------------------
#     DATABASE_URL: str = os.getenv(
#         "DATABASE_URL",
#         "postgresql+asyncpg://postgres:1234@localhost:5432/RestaurantManagementSystem",
#     )

#     # --------------------------------------------------
#     # Redis
#     # --------------------------------------------------
#     REDIS_URL: str = os.getenv(
#         "REDIS_URL",
#         "redis://localhost:6379/0",
#     )

#     # --------------------------------------------------
#     # JWT
#     # --------------------------------------------------
#     SECRET_KEY: str = os.getenv(
#         "SECRET_KEY",
#         "changeme-set-a-real-secret-key-in-env",
#     )

#     ALGORITHM: str = os.getenv(
#         "ALGORITHM",
#         "HS256",
#     )

#     ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
#         os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
#     )

#     # --------------------------------------------------
#     # App
#     # --------------------------------------------------
#     APP_ENV: str = os.getenv(
#         "APP_ENV",
#         "development",
#     )

#     DEBUG: bool = (
#         os.getenv("DEBUG", "False").lower() == "true"
#     )

#     # --------------------------------------------------
#     # CORS
#     # --------------------------------------------------
#     ALLOWED_ORIGINS: list[str] = [
#         origin.strip()
#         for origin in os.getenv(
#             "ALLOWED_ORIGINS",
#             "http://localhost:5173,http://localhost:5174,http://localhost:3000",
#         ).split(",")
#         if origin.strip()
#     ]

#     # --------------------------------------------------
#     # SMTP
#     # --------------------------------------------------
#     SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.zoho.in")

#     SMTP_PORT: int = int(
#         os.getenv("SMTP_PORT", "465")
#     )

#     SMTP_USER: str = os.getenv(
#         "SMTP_USER",
#         os.getenv(
#             "ZOHO_USER",
#             "mohitjoshi787898@gmail.com",
#         ),
#     )

#     SMTP_PASSWORD: str = os.getenv(
#         "SMTP_PASSWORD",
#         os.getenv(
#             "ZOHO_PASS",
#             "fQCBj9YFu1ne",
#         ),
#     )

#     SMTP_FROM: str = os.getenv(
#         "SMTP_FROM",
#         f"Siara <{os.getenv('SMTP_USER','sales@siaratechnology.com')}>",
#     )


# settings = Settings()




import os
from dotenv import load_dotenv
from pathlib import Path


# ============================================================
# LOAD .ENV
# ============================================================

# Project structure:
#
# RestaurantBackend/
# ├── .env
# └── app/
#     └── core/
#         └── config.py
#
# config.py -> core -> app -> RestaurantBackend
#
# Therefore:
# parent.parent.parent = project root

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:

    # ========================================================
    # DATABASE
    # ========================================================

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:1234@localhost:5432/RestaurantManagementSystem",
    )

    # ========================================================
    # REDIS
    # ========================================================

    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0",
    )

    # ========================================================
    # JWT
    # ========================================================

    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "changeme-set-a-real-secret-key-in-env",
    )

    ALGORITHM: str = os.getenv(
        "ALGORITHM",
        "HS256",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "60",
        )
    )

    # ========================================================
    # APP
    # ========================================================

    APP_ENV: str = os.getenv(
        "APP_ENV",
        "development",
    )

    DEBUG: bool = (
        os.getenv(
            "DEBUG",
            "False",
        ).lower()
        == "true"
    )

    # ========================================================
    # CORS
    # ========================================================

    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:5174,http://localhost:3000",
        ).split(",")
        if origin.strip()
    ]

    # ========================================================
    # SMTP
    # ========================================================

    SMTP_HOST: str = os.getenv(
        "SMTP_HOST",
        "smtp.zoho.in",
    )

    SMTP_PORT: int = int(
        os.getenv(
            "SMTP_PORT",
            "465",
        )
    )

    SMTP_USER: str = os.getenv(
        "SMTP_USER",
        os.getenv("ZOHO_USER", ""),
    )

    SMTP_PASSWORD: str = os.getenv(
        "SMTP_PASSWORD",
        os.getenv("ZOHO_PASS", ""),
    )

    SMTP_FROM: str = os.getenv(
        "SMTP_FROM",
        "",
    )

    # ========================================================
    # AWS S3
    # ========================================================

    AWS_ACCESS_KEY_ID: str = os.getenv(
        "AWS_ACCESS_KEY_ID",
        "",
    )

    AWS_SECRET_ACCESS_KEY: str = os.getenv(
        "AWS_SECRET_ACCESS_KEY",
        "",
    )

    AWS_REGION: str = os.getenv(
        "AWS_REGION",
        "ap-south-1",
    )

    AWS_S3_BUCKET: str = os.getenv(
        "AWS_S3_BUCKET",
        "restaurantsiara",
    )


# ============================================================
# SHARED SETTINGS INSTANCE
# ============================================================

settings = Settings()