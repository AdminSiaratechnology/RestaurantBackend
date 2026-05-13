from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ✅ Import ALL models here so SQLAlchemy can register them
# (VERY IMPORTANT for metadata & migrations)

from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.brand.model import Brand
from app.accounts.branch.model import Branch
from app.accounts.table.model import Table
from app.accounts.category.model import Category
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.staff.model import Staff