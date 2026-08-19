"""
Verification test for Customer Visit History creation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import app.db.base  # noqa
from app.accounts.crm.customer_history.checkout_service import handle_customer_and_visit
from app.accounts.customer.service import find_or_create_customer


async def test_visit_creation():
    print("=== Testing Customer & Visit History Creation ===")

    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    mock_db.scalar.return_value = None
    mock_db.flush.return_value = None
    mock_db.refresh.return_value = None
    mock_db.add.return_value = None

    # Test 1: Customer without phone/email (Walk-in Guest)
    customer, created = await find_or_create_customer(
        db=mock_db,
        client_id=1,
        branch_id=1,
        branch_name="Main Branch",
        name="Walk-in Guest",
        phone=None,
        email=None
    )

    assert customer is not None
    assert "GUEST" in customer.phone
    print(f"[Test 1 Passed] Walk-in customer created: ID={customer.id}, Name={customer.name}, Phone={customer.phone}")

    # Test 2: Complete checkout with handle_customer_and_visit
    result_customer = await handle_customer_and_visit(
        db=mock_db,
        client_id=1,
        branch_id=1,
        branch_name="Main Branch",
        order_id=10,
        bill_id=20,
        total_amount=500.0,
        discount=50.0,
        tax=25.0,
        payment_method="UPI",
        table_name="T-1",
        visit_type="Dine-In",
        customer_name=None,
        customer_phone=None
    )

    assert result_customer is not None
    print(f"[Test 2 Passed] Visit history handles guest checkout successfully! Customer={result_customer.name}")
    print("=== ALL VISIT HISTORY TESTS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(test_visit_creation())
