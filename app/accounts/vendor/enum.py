from enum import Enum


class VendorStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class VendorType(str, Enum):
    supplier = "supplier"
    manufacturer = "manufacturer"
    distributor = "distributor"
    service_provider = "service_provider"


class PaymentMethod(str, Enum):
    cash = "cash"
    credit = "credit"
    bank_transfer = "bank_transfer"
    upi = "upi"
    cheque = "cheque"