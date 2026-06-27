from enum import Enum


class PurchaseOrderStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    ordered = "ordered"
    partially_received = "partially_received"
    received = "received"
    cancelled = "cancelled"