import os
from dotenv import load_dotenv
from pathlib import Path

# ✅ Load .env from project root (RestaurantBackend/.env)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # ----- Database -----
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:1234@localhost:5432/RestaurantManagementSystem"
    )

    # ----- JWT / Auth -----
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "changeme-set-a-real-secret-key-in-env"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # ----- App -----
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # ----- CORS -----
    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:5174,http://localhost:3000"
        ).split(",")
        if origin.strip()
    ]


# ✅ Single shared instance — import this everywhere
settings = Settings()
