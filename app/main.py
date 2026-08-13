from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base
from app.db.config import engine
from app.models import *
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from app.core.redis import redis_client, close_redis_connection, check_redis_health



# from app.accounts.auth.routers import auth,  superadmin, partner, staff, client
from app.accounts.auth.routers import router as auth_router
from app.accounts.superadmin.routers import router as superadmin_router
from app.accounts.client.router import router as client_router
from app.accounts.category.routers import router as category_router
from app.accounts.item.routers import router as item_router
from app.accounts.brand.router import router as brand_router
from app.accounts.pricing.routers import router as pricing_router
from app.accounts.branch.router import router as branch_router
from app.accounts.table.router import router as table_router
from app.accounts.partner.router import router as partner_router
from app.accounts.chef.router import router as chef_router
from app.accounts.customer.router import router as customer_router
from app.accounts.order.router  import router as order_router
from app.accounts.waiter.router import router as waiter_router
from app.accounts.orderstatus.routers import router as orderstatus_router
from app.accounts.inventory.router import router as inventory_router
from app.accounts.deshboard.router import router as deshboard_router, today_router
from app.accounts.auditlog.router import router as auditlog_router
from app.accounts.permission.routers import router as permission_router
from app.accounts.tax.router import router as tax_router
from app.accounts.bill.router import router as bill_router
from app.accounts.offer.router import router as offer_router
from app.accounts.legaldetails.router import router as legaldetails_router
from app.accounts.payment.router import router as payment_router
from app.accounts.ingredient.router import router as ingredient_router
from fastapi.staticfiles import StaticFiles
from app.accounts.rep_financial.router import router as rep_financial_router
from app.accounts.rep_sales.router import router as rep_sales_router
from app.accounts.rep_menu.router import router as rep_menu_router
from app.accounts.rep_inventory.router import router as rep_inventory_router
from app.accounts.forget_password.router import router as forget_password_router
from app.accounts.change_password.router import router as change_password_router
from app.accounts.total_sales.router import router as total_sales_router
from app.accounts.rep_payment.router import router as rep_payment_router
from app.accounts.purchaseorder.router import router as purchas_order_router
from app.accounts.vendor.router import router as vendor_router
from app.accounts.uploads.router import router as upload_router
from app.accounts.crm.customer_history.router import router as customer_history_router
from app.accounts.crm.wallet.router import router as wallet_router
from app.accounts.crm.loyalty.router import router as loyalty_router
from app.accounts.crm.campaigns.router import router as campaigns_router
from app.accounts.crm.rank_rules.router import router as rank_rules_router
from app.accounts.settings.router import router as settings_router
from app.accounts.crm.loyalty.conversion_rule.router import router as conversion_rule_router


app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",  # Vite dev server
        "http://localhost:3000",  # CRA dev server
        "https://restaurantsiara.netlify.app",
        "https://restaurantsiaralive.netlify.app",
        "https://rmssuperadminn.netlify.app",
        "https://dx9mtcpd-5173.inc1.devtunnels.ms",
        
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.db.create_indexes import create_db_indexes

# @app.on_event("startup")
# async def startup():
#     print("STARTUP BEGIN")

#     async with engine.begin() as conn:
#         print("DB CONNECTED")

#         await conn.run_sync(Base.metadata.create_all)

#         print("TABLES CREATED")

#     await create_db_indexes()

#     await check_redis_health()

#     print("STARTUP END")


@app.on_event("startup")
async def startup():
    print("STARTUP BEGIN")

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        print("Database Connected")

        await create_db_indexes()

        await check_redis_health()

        print("STARTUP END")

    except Exception as e:
        print("DATABASE ERROR:", repr(e))
        raise


@app.on_event("shutdown")
async def shutdown():
    await close_redis_connection()





# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     await redis_client.ping()
#     print("✅ Connected to Memurai")

#     yield

#     # Shutdown
#     await redis_client.aclose()
#     print("🔴 Redis connection closed")

# app = FastAPI(lifespan=lifespan)


app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads",
)

app.include_router(auth_router)
app.include_router(superadmin_router)
app.include_router(partner_router)
app.include_router(client_router)
app.include_router(category_router)
app.include_router(brand_router)
app.include_router(permission_router)
app.include_router(chef_router)
app.include_router(branch_router)
app.include_router(item_router)
app.include_router(pricing_router)
app.include_router(table_router)
app.include_router(waiter_router)
app.include_router(customer_router)
app.include_router(order_router)
app.include_router(orderstatus_router)
app.include_router(inventory_router)
app.include_router(tax_router)
app.include_router(bill_router)
app.include_router(offer_router)
app.include_router(deshboard_router)
app.include_router(today_router)
app.include_router(legaldetails_router)
app.include_router(auditlog_router)
app.include_router(payment_router)
app.include_router(ingredient_router)
app.include_router(rep_financial_router)
app.include_router(rep_sales_router)
app.include_router(rep_menu_router)
app.include_router(rep_inventory_router)
app.include_router(forget_password_router)
app.include_router(change_password_router)
app.include_router(total_sales_router)
app.include_router(rep_payment_router)
app.include_router(purchas_order_router)
app.include_router(vendor_router)
app.include_router(upload_router)
app.include_router(customer_history_router)
app.include_router(wallet_router)
app.include_router(loyalty_router)
app.include_router(campaigns_router)
app.include_router(rank_rules_router)
app.include_router(settings_router)
app.include_router(conversion_rule_router)