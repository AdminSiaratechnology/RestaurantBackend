# from logging.config import fileConfig

# from sqlalchemy import pool
# from sqlalchemy.engine import Connection
# from sqlalchemy.ext.asyncio import async_engine_from_config

# from alembic import context

# # ✅ Import Base
# from app.db.base import Base

# # ✅ Import ALL models here
# # VERY IMPORTANT
# from app.accounts.table.model import Table
# from app.accounts.branch.model import Branch
# from app.accounts.client.model import Client

# # Alembic Config
# config = context.config

# from app.core.settings import settings

# config.set_main_option(
#     "sqlalchemy.url",
#     settings.DATABASE_URL
# )

# # Logging
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# # Metadata
# target_metadata = Base.metadata


# # ======================================================
# # OFFLINE MODE
# # ======================================================
# def run_migrations_offline() -> None:
#     url = config.get_main_option("sqlalchemy.url")

#     context.configure(
#         url=url,
#         target_metadata=target_metadata,
#         literal_binds=True,
#         dialect_opts={"paramstyle": "named"},
#         compare_type=True,
#     )

#     with context.begin_transaction():
#         context.run_migrations()


# # ======================================================
# # ONLINE MODE
# # ======================================================
# def do_run_migrations(connection: Connection) -> None:
#     context.configure(
#         connection=connection,
#         target_metadata=target_metadata,
#         compare_type=True,
#     )

#     with context.begin_transaction():
#         context.run_migrations()


# async def run_migrations_online() -> None:
#     connectable = async_engine_from_config(
#         config.get_section(config.config_ini_section),
#         prefix="sqlalchemy.",
#         poolclass=pool.NullPool,
#         future=True,
#     )

#     async with connectable.connect() as connection:
#         await connection.run_sync(do_run_migrations)

#     await connectable.dispose()


# # ======================================================
# # RUNNER
# # ======================================================
# if context.is_offline_mode():
#     run_migrations_offline()
# else:
#     import asyncio

#     asyncio.run(run_migrations_online())



from logging.config import fileConfig
import asyncio
from urllib.parse import urlparse

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# ============================================================
# IMPORT BASE
# ============================================================
from app.db.base import Base

# ============================================================
# IMPORT ALL MODELS
# ============================================================
from app.accounts.table.model import Table
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client

# ============================================================
# SETTINGS
# ============================================================
from app.core.settings import settings


# ============================================================
# ALEMBIC CONFIG
# ============================================================
config = context.config

DATABASE_URL = settings.DATABASE_URL

config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL,
)


# ============================================================
# LOGGING
# ============================================================
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ============================================================
# METADATA
# ============================================================
target_metadata = Base.metadata


# ============================================================
# SSL CONFIGURATION
# ============================================================
def get_connect_args() -> dict:
    """
    Local PostgreSQL:
        SSL disabled

    Remote PostgreSQL:
        SSL enabled
    """

    parsed_url = urlparse(DATABASE_URL)

    hostname = parsed_url.hostname

    if hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        return {}

    return {
        "ssl": True,
        "command_timeout": 60,
    }


# ============================================================
# OFFLINE MODE
# ============================================================
def run_migrations_offline() -> None:

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# MIGRATION CALLBACK
# ============================================================
def do_run_migrations(
    connection: Connection,
) -> None:

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# ONLINE MODE
# ============================================================
async def run_migrations_online() -> None:

    connect_args = get_connect_args()

    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    try:

        async with connectable.connect() as connection:

            await connection.run_sync(
                do_run_migrations
            )

    finally:

        await connectable.dispose()


# ============================================================
# RUNNER
# ============================================================
if context.is_offline_mode():

    run_migrations_offline()

else:

    asyncio.run(
        run_migrations_online()
    )