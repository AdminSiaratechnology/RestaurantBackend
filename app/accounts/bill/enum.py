from enum import Enum


class PaymentStatus(str, Enum):
    cancel = "cancel"
    pending = "pending"
    complete = "complete"
    edited = "edited"