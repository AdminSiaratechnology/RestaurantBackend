"""
app/accounts/customer/test_customer_type.py

Comprehensive test suite for Customer Type classification logic:
1. Gold rank -> VIP (Highest priority, regardless of visit count)
2. If NOT Gold:
   - visit_count > 2 -> Regular
   - visit_count <= 2 -> New
"""

import sys
import os

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.accounts.customer.model import CustomerTypeEnum
from app.accounts.customer.service import determine_customer_type


def test_user_provided_test_cases():
    """
    Test all 9 cases from the user test table:
    | Rank   | Visit Count | Expected Customer Type |
    | Gold   |           0 | VIP                    |
    | Gold   |           1 | VIP                    |
    | Gold   |           2 | VIP                    |
    | Gold   |          10 | VIP                    |
    | Silver |           0 | New                    |
    | Silver |           2 | New                    |
    | Silver |           3 | Regular                |
    | Bronze |           1 | New                    |
    | Bronze |           3 | Regular                |
    """
    assert determine_customer_type("Gold", 0) == CustomerTypeEnum.VIP
    assert determine_customer_type("Gold", 1) == CustomerTypeEnum.VIP
    assert determine_customer_type("Gold", 2) == CustomerTypeEnum.VIP
    assert determine_customer_type("Gold", 10) == CustomerTypeEnum.VIP

    assert determine_customer_type("Silver", 0) == CustomerTypeEnum.NEW
    assert determine_customer_type("Silver", 2) == CustomerTypeEnum.NEW
    assert determine_customer_type("Silver", 3) == CustomerTypeEnum.REGULAR

    assert determine_customer_type("Bronze", 1) == CustomerTypeEnum.NEW
    assert determine_customer_type("Bronze", 3) == CustomerTypeEnum.REGULAR


def test_gold_priority_with_edge_cases():
    """
    Gold rank must ALWAYS evaluate to VIP, regardless of visit count or casing.
    """
    # Case insensitivity & trimming
    assert determine_customer_type("gold", 0) == CustomerTypeEnum.VIP
    assert determine_customer_type("GOLD", 50) == CustomerTypeEnum.VIP
    assert determine_customer_type("  Gold  ", 0) == CustomerTypeEnum.VIP
    assert determine_customer_type("gold", 100) == CustomerTypeEnum.VIP


def test_non_gold_visit_count_boundary():
    """
    Non-Gold ranks:
    <= 2 visits -> New
    > 2 visits  -> Regular
    """
    # Boundary: 2 vs 3
    assert determine_customer_type("Bronze", 0) == CustomerTypeEnum.NEW
    assert determine_customer_type("Bronze", 2) == CustomerTypeEnum.NEW
    assert determine_customer_type("Bronze", 3) == CustomerTypeEnum.REGULAR
    assert determine_customer_type("Bronze", 4) == CustomerTypeEnum.REGULAR
    assert determine_customer_type("Bronze", 100) == CustomerTypeEnum.REGULAR

    assert determine_customer_type("Silver", 1) == CustomerTypeEnum.NEW
    assert determine_customer_type("Silver", 2) == CustomerTypeEnum.NEW
    assert determine_customer_type("Silver", 3) == CustomerTypeEnum.REGULAR
    assert determine_customer_type("Silver", 25) == CustomerTypeEnum.REGULAR

    # Platinum / Other ranks if any
    assert determine_customer_type("Platinum", 1) == CustomerTypeEnum.NEW
    assert determine_customer_type("Platinum", 2) == CustomerTypeEnum.NEW
    assert determine_customer_type("Platinum", 3) == CustomerTypeEnum.REGULAR


def test_none_and_default_handling():
    """
    Handles None or missing rank gracefully.
    """
    assert determine_customer_type(None, 0) == CustomerTypeEnum.NEW
    assert determine_customer_type(None, 1) == CustomerTypeEnum.NEW
    assert determine_customer_type(None, 2) == CustomerTypeEnum.NEW
    assert determine_customer_type(None, 3) == CustomerTypeEnum.REGULAR
    assert determine_customer_type("", 5) == CustomerTypeEnum.REGULAR


if __name__ == "__main__":
    test_user_provided_test_cases()
    test_gold_priority_with_edge_cases()
    test_non_gold_visit_count_boundary()
    test_none_and_default_handling()
    print("All customer type classification tests passed successfully!")
