from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base
from app.db.config import engine
from app.models import *
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
from app.accounts.customer.router import router as customer_router
from app.accounts.order.router  import router as order_router
from app.accounts.orderstatus.routers import router as orderstatus_router
from app.accounts.inventory.router import router as inventory_router
from app.accounts.deshboard.router import router as deshboard_router
from app.accounts.auditlog.router import router as auditlog_router

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # CRA dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ✅ include routers AFTER app creation
# app.include_router(auth.router)
# app.include_router(superadmin.router)
# app.include_router(partner.router)
# app.include_router(client.router)
# app.include_router(staff.router)
app.include_router(auth_router)
app.include_router(superadmin_router)
app.include_router(partner_router)
app.include_router(client_router)
app.include_router(category_router)
app.include_router(brand_router)
app.include_router(branch_router)
app.include_router(item_router)
app.include_router(pricing_router)
app.include_router(table_router)
app.include_router(customer_router)
app.include_router(order_router)
app.include_router(orderstatus_router)
app.include_router(inventory_router)
app.include_router(deshboard_router)
app.include_router(auditlog_router)