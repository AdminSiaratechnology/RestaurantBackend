from sqlalchemy.orm import declarative_base

Base = declarative_base()


# =========================================================
# ACCOUNT & DOMAIN MODELS
# =========================================================

try:
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
    from app.accounts.customer.model import Customer
    from app.accounts.permission.model import StaffPermission
    from app.accounts.inventory.model import InventoryItem, Godown
    from app.accounts.order.model import Order, OrderItem
    from app.accounts.bill.model import Bill
    from app.accounts.payment.model import Payment
    from app.accounts.offer.model import Offer
    from app.accounts.tax.model import TaxBillingSetting
    from app.accounts.legaldetails.model import LegalCompliance
    from app.accounts.auditlog.model import AuditLog
    from app.accounts.ingredient.model import ItemIngredient
    from app.accounts.bom.model import MenuItemBOM
    from app.accounts.forget_password.model import PasswordResetOTP
    from app.accounts.vendor.model import Vendor
    from app.accounts.crm.customer_history.model import CustomerVisitHistory
    from app.accounts.crm.events.model import CRMProcessedEvent
    from app.accounts.crm.loyalty.model import CustomerLoyaltyAccount, LoyaltyTransaction
    from app.accounts.crm.wallet.model import CustomerWalletAccount, WalletTransaction
    from app.accounts.crm.campaigns.model import Campaign, CampaignLog, CustomerCoupon
    from app.accounts.crm.rank_rules.model import CRMBranchRankRule
    from app.accounts.crm.loyalty.conversion_rule.model import LoyaltyConversionRule
    from app.accounts.crm.loyalty.wallet_discount_rule.model import WalletDiscountRule
    from app.accounts.crm.customer_notes.model import CustomerNote
except ImportError:
    pass



# =========================================================
# PURCHASE
# =========================================================

try:
    from app.accounts.purchase.model import (
        PurchaseEntry,
        PurchaseEntryItem,
        BranchPurchaseInvoiceCounter,
    )
except ImportError:
    pass
