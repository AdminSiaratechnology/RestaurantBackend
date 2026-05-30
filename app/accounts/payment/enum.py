from enum import Enum


class PaymentMethod(str, Enum):

    cash = "cash"

    card = "card"

    upi = "upi"

    credit = "credit"

    split = "split"