from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import Depends
from typing import AsyncGenerator, Annotated
import os

# ✅ Use ENV variable (NEVER hardcode in production)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # "postgresql+asyncpg://postgres:1234@localhost/RestaurantManagementSystem"
    "postgresql+asyncpg://restaurant_user:UxE0lcJTZUtoOnsclxAqTAEB1InjFFlI@dpg-ct123abc-a.oregon-postgres.render.com/restaurant_management_system"
)

# 🔹 Create async engine (optimized)
# engine = create_async_engine(
#     DATABASE_URL,
#     echo=False,  # ❌ disable in production (enable only for debugging)
#     pool_size=10,          # ✅ connection pool
#     max_overflow=20,       # ✅ extra connections
#     pool_timeout=30,       # ✅ wait time before timeout
#     pool_recycle=1800,     # ✅ recycle connections (avoid stale)
#     future=True,
# )

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    future=True,
    connect_args={
        "ssl": True
    }
)

# 🔹 Create async session maker
async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# 🔹 Dependency for FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()  # 🔥 IMPORTANT
            raise
        finally:
            await session.close()     # 🔥 SAFE CLEANUP


# ✅ Type annotation (clean injection)
SessionDep = Annotated[AsyncSession, Depends(get_db)]