# from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
# from fastapi import Depends
# from typing import AsyncGenerator, Annotated
# import ssl

# from app.core.settings import settings  # ✅ Load from .env via central settings

# DATABASE_URL = settings.DATABASE_URL

# # 🔹 Auto-detect Render.com (needs SSL)
# is_render = "render.com" in DATABASE_URL

# ssl_context = ssl.create_default_context()
# ssl_context.check_hostname = False
# ssl_context.verify_mode = ssl.CERT_NONE

# engine = create_async_engine(
#     DATABASE_URL,
#     echo=settings.DEBUG,       # ✅ Only verbose in debug/dev mode
#     pool_pre_ping=True,
#     pool_recycle=300,
#     future=True,
#     connect_args={
#         "ssl": True
#     } if is_render else {}
# )

# # 🔹 Create async session maker
# async_session = async_sessionmaker(
#     bind=engine,
#     expire_on_commit=False,
#     class_=AsyncSession
# )


# # 🔹 Dependency for FastAPI routes
# async def get_db() -> AsyncGenerator[AsyncSession, None]:
#     async with async_session() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()  # 🔥 IMPORTANT
#             raise
#         finally:
#             await session.close()     # 🔥 SAFE CLEANUP


# # ✅ Type annotation (clean injection)
# SessionDep = Annotated[AsyncSession, Depends(get_db)]




from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import Depends
from typing import AsyncGenerator, Annotated
import ssl

from app.core.settings import settings

DATABASE_URL = settings.DATABASE_URL

ssl_context = ssl.create_default_context()

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "ssl": ssl_context
    } if "render.com" in DATABASE_URL else {}
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

SessionDep = Annotated[AsyncSession, Depends(get_db)]