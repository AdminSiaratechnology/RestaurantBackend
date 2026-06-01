from enum import Enum


class PaymentStatus(str, Enum):
    cancel = "canceled"
    pending = "pending"
    complete = "complete"