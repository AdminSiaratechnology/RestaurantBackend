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
from app.accounts.order.model import Order, OrderItem
from app.accounts.customer.model import Customer
from app.accounts.permission.model import StaffPermission
from app.accounts.inventory.model import InventoryItem
from app.accounts.auditlog.model import AuditLog
from app.accounts.bill.model import Bill
from app.accounts.payment.model import Payment
from app.accounts.offer.model import Offer
from app.accounts.tax.model import TaxBillingSetting
from app.accounts.legaldetails.model import LegalCompliance
from app.accounts.ingredient.model import ItemIngredient
from app.accounts.forget_password.model import PasswordResetOTP
from app.accounts.inventory.model import InventoryItem
from app.accounts.inventory.model import Godown
from app.accounts.purchaseorder.model import PurchaseOrder, PurchaseOrderItem
from app.accounts.bom.model import MenuItemBOM
from app.accounts.vendor.model import Vendor
from app.accounts.crm.customer_history.model import CustomerVisitHistory