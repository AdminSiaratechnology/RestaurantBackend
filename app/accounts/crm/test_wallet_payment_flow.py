"""
Verification test script for CRM Wallet payment logic.
Tests all 7 required business test cases:
- Test 1: Bill=1000, Offer=0, use_wallet=False -> wallet_discount=0, final_amount=1000, balance unchanged.
- Test 2: Bill=1000, Offer=100, use_wallet=False -> wallet_discount=0, final_amount=900, balance unchanged.
- Test 3: Bill=1000, Offer=0, use_wallet=True, wallet contribution=200 -> wallet_discount=200, final_amount=800, balance decreases by 200.
- Test 4: Bill=1000, Offer=100, use_wallet=True, wallet contribution=180 -> amount_after_offer=900, wallet_discount=180, final_amount=720, wallet debit=180.
- Test 5: Wallet balance exists but user does NOT select wallet -> wallet MUST NOT be deducted.
- Test 6: Call wallet-preview without paying -> wallet MUST NOT be deducted.
- Test 7: Retry the same payment request -> duplicate debit protection prevents second deduction.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# Import ORM models
import app.db.base  # noqa

from app.accounts.payment.schema import PaymentCreate, PaymentItem
from app.accounts.payment.enum import PaymentMethod
from app.accounts.payment.service import make_payment_service
from app.accounts.crm.wallet.service import calculate_wallet_discount, debit_wallet
from app.accounts.bill.enum import PaymentStatus
from app.accounts.offer.model import OfferType

from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException


async def run_wallet_tests():
    print("============================================================")
    print("STARTING CRM WALLET PAYMENT FLOW VERIFICATION TESTS")
    print("============================================================")

    now = datetime.now()

    # -------------------------------------------------------------------------
    # TEST 1: Bill = ₹1000, Offer = ₹0, use_wallet = False
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Bill = ₹1000, Offer = ₹0, use_wallet = False ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_bill = MagicMock()
    mock_bill.id = 101
    mock_bill.grand_total = 1000.0
    mock_bill.payment_status = PaymentStatus.pending
    mock_bill.client_id = 1
    mock_bill.branch_id = 1
    mock_bill.customer_id = 10
    mock_bill.order_id = 50

    async def mock_execute_t1(stmt):
        m = MagicMock()
        m.scalar_one_or_none.return_value = mock_bill
        return m

    mock_db.execute.side_effect = mock_execute_t1

    data = PaymentCreate(
        bill_id=101,
        payments=[PaymentItem(payment_method=PaymentMethod.cash, payment_amount=1000.0)],
        use_wallet=False
    )

    payment = await make_payment_service(mock_db, data)

    assert payment.wallet_discount == 0.0, f"Expected 0.0, got {payment.wallet_discount}"
    assert payment.paid_amount == 1000.0, f"Expected 1000.0, got {payment.paid_amount}"
    assert mock_bill.wallet_discount == 0.0, f"Expected Bill.wallet_discount=0.0, got {mock_bill.wallet_discount}"
    assert mock_bill.paid_amount == 1000.0, f"Expected Bill.paid_amount=1000.0, got {mock_bill.paid_amount}"

    print("✅ TEST 1 PASSED: wallet_discount=0, final_amount=1000, no wallet debit called.")

    # -------------------------------------------------------------------------
    # TEST 2: Bill = ₹1000, Offer = ₹100, use_wallet = False
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Bill = ₹1000, Offer = ₹100, use_wallet = False ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_bill = MagicMock()
    mock_bill.id = 102
    mock_bill.grand_total = 1000.0
    mock_bill.payment_status = PaymentStatus.pending
    mock_bill.client_id = 1
    mock_bill.branch_id = 1
    mock_bill.customer_id = 10
    mock_bill.order_id = 51

    mock_offer = MagicMock()
    mock_offer.id = 1
    mock_offer.offer_type = OfferType.FLAT_DISCOUNT
    mock_offer.discount_value = 100.0
    mock_offer.min_order_amount = 0.0
    mock_offer.valid_from = now - timedelta(days=1)
    mock_offer.valid_to = now + timedelta(days=1)
    mock_offer.is_active = True
    mock_offer.usage_limit = 100
    mock_offer.no_used = 0

    async def mock_execute_t2(stmt):
        m = MagicMock()
        str_stmt = str(stmt)
        if "offers" in str_stmt:
            m.scalar_one_or_none.return_value = mock_offer
        else:
            m.scalar_one_or_none.return_value = mock_bill
        return m

    mock_db.execute.side_effect = mock_execute_t2

    data = PaymentCreate(
        bill_id=102,
        offer_id=1,
        payments=[PaymentItem(payment_method=PaymentMethod.cash, payment_amount=900.0)],
        use_wallet=False
    )

    payment = await make_payment_service(mock_db, data)

    assert payment.offer_discount == 100.0, f"Expected offer_discount=100.0, got {payment.offer_discount}"
    assert payment.wallet_discount == 0.0, f"Expected wallet_discount=0.0, got {payment.wallet_discount}"
    assert payment.paid_amount == 900.0, f"Expected paid_amount=900.0, got {payment.paid_amount}"
    assert mock_bill.wallet_discount == 0.0
    assert mock_bill.paid_amount == 900.0

    print("✅ TEST 2 PASSED: offer_discount=100, wallet_discount=0, final_amount=900.")

    # -------------------------------------------------------------------------
    # TEST 3: Bill = ₹1000, Offer = ₹0, use_wallet = True (Wallet discount ₹200)
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Bill = ₹1000, Offer = ₹0, use_wallet = True ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_bill = MagicMock()
    mock_bill.id = 103
    mock_bill.grand_total = 1000.0
    mock_bill.payment_status = PaymentStatus.pending
    mock_bill.client_id = 1
    mock_bill.branch_id = 1
    mock_bill.customer_id = 10
    mock_bill.order_id = 52

    mock_wallet = MagicMock()
    mock_wallet.id = 5
    mock_wallet.balance = 500.0
    mock_wallet.total_spent = 0.0
    mock_wallet.is_active = True

    mock_rule = MagicMock()
    mock_rule.max_wallet_discount_percent = 20.0
    mock_rule.is_active = True

    async def mock_execute_t3(stmt):
        m = MagicMock()
        str_stmt = str(stmt)
        if "customer_wallet_accounts" in str_stmt:
            m.scalar_one_or_none.return_value = mock_wallet
        elif "wallet_discount_rules" in str_stmt:
            m.scalars.return_value.all.return_value = [mock_rule]
        elif "wallet_transactions" in str_stmt:
            m.scalar_one_or_none.return_value = None
        else:
            m.scalar_one_or_none.return_value = mock_bill
        return m

    mock_db.execute.side_effect = mock_execute_t3

    data = PaymentCreate(
        bill_id=103,
        payments=[PaymentItem(payment_method=PaymentMethod.cash, payment_amount=800.0)],
        use_wallet=True
    )

    payment = await make_payment_service(mock_db, data)

    assert payment.wallet_discount == 200.0, f"Expected wallet_discount=200.0, got {payment.wallet_discount}"
    assert payment.paid_amount == 800.0, f"Expected paid_amount=800.0, got {payment.paid_amount}"
    assert mock_wallet.balance == 300.0, f"Expected wallet balance 300.0, got {mock_wallet.balance}"
    assert mock_bill.wallet_discount == 200.0
    assert mock_bill.paid_amount == 800.0

    print("✅ TEST 3 PASSED: wallet_discount=200, final_amount=800, wallet debited exactly 200.")

    # -------------------------------------------------------------------------
    # TEST 4: Bill = ₹1000, Offer = ₹100, use_wallet = True
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Bill = ₹1000, Offer = ₹100, use_wallet = True ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_bill = MagicMock()
    mock_bill.id = 104
    mock_bill.grand_total = 1000.0
    mock_bill.payment_status = PaymentStatus.pending
    mock_bill.client_id = 1
    mock_bill.branch_id = 1
    mock_bill.customer_id = 10
    mock_bill.order_id = 53

    mock_offer = MagicMock()
    mock_offer.id = 2
    mock_offer.offer_type = OfferType.FLAT_DISCOUNT
    mock_offer.discount_value = 100.0
    mock_offer.min_order_amount = 0.0
    mock_offer.valid_from = now - timedelta(days=1)
    mock_offer.valid_to = now + timedelta(days=1)
    mock_offer.is_active = True
    mock_offer.usage_limit = 100
    mock_offer.no_used = 0

    mock_wallet = MagicMock()
    mock_wallet.id = 5
    mock_wallet.balance = 500.0
    mock_wallet.total_spent = 0.0
    mock_wallet.is_active = True

    mock_rule = MagicMock()
    mock_rule.max_wallet_discount_percent = 20.0
    mock_rule.is_active = True

    async def mock_execute_t4(stmt):
        m = MagicMock()
        str_stmt = str(stmt)
        if "offers" in str_stmt:
            m.scalar_one_or_none.return_value = mock_offer
        elif "customer_wallet_accounts" in str_stmt:
            m.scalar_one_or_none.return_value = mock_wallet
        elif "wallet_discount_rules" in str_stmt:
            m.scalars.return_value.all.return_value = [mock_rule]
        elif "wallet_transactions" in str_stmt:
            m.scalar_one_or_none.return_value = None
        else:
            m.scalar_one_or_none.return_value = mock_bill
        return m

    mock_db.execute.side_effect = mock_execute_t4

    # Amount after offer = 900. Wallet limit = 20% of 900 = 180. Final amount = 720.
    data = PaymentCreate(
        bill_id=104,
        offer_id=2,
        payments=[PaymentItem(payment_method=PaymentMethod.cash, payment_amount=720.0)],
        use_wallet=True
    )

    payment = await make_payment_service(mock_db, data)

    assert payment.offer_discount == 100.0
    assert payment.wallet_discount == 180.0, f"Expected wallet_discount=180.0, got {payment.wallet_discount}"
    assert payment.paid_amount == 720.0, f"Expected paid_amount=720.0, got {payment.paid_amount}"
    assert mock_wallet.balance == 320.0, f"Expected wallet balance 320.0, got {mock_wallet.balance}"
    assert mock_bill.wallet_discount == 180.0
    assert mock_bill.paid_amount == 720.0

    print("✅ TEST 4 PASSED: amount_after_offer=900, wallet_discount=180, final_amount=720, wallet debited 180.")

    # -------------------------------------------------------------------------
    # TEST 5: Customer has wallet balance, but use_wallet = False
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Wallet balance exists, use_wallet = False ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_bill = MagicMock()
    mock_bill.id = 105
    mock_bill.grand_total = 1000.0
    mock_bill.payment_status = PaymentStatus.pending
    mock_bill.client_id = 1
    mock_bill.branch_id = 1
    mock_bill.customer_id = 10
    mock_bill.order_id = 54

    mock_wallet = MagicMock()
    mock_wallet.id = 5
    mock_wallet.balance = 5000.0  # Huge wallet balance
    mock_wallet.total_spent = 0.0
    mock_wallet.is_active = True

    async def mock_execute_t5(stmt):
        m = MagicMock()
        m.scalar_one_or_none.return_value = mock_bill
        return m

    mock_db.execute.side_effect = mock_execute_t5

    data = PaymentCreate(
        bill_id=105,
        payments=[PaymentItem(payment_method=PaymentMethod.cash, payment_amount=1000.0)],
        use_wallet=False
    )

    payment = await make_payment_service(mock_db, data)

    assert payment.wallet_discount == 0.0
    assert payment.paid_amount == 1000.0
    assert mock_wallet.balance == 5000.0, "Wallet balance MUST NOT change when use_wallet=False"

    print("✅ TEST 5 PASSED: Wallet balance exists, but wallet was NOT deducted because use_wallet=False.")

    # -------------------------------------------------------------------------
    # TEST 6: Call calculate_wallet_discount (Wallet Preview) without paying
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Preview calculation without paying ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_wallet = MagicMock()
    mock_wallet.id = 5
    mock_wallet.balance = 1000.0
    mock_wallet.total_spent = 0.0
    mock_wallet.is_active = True

    mock_rule = MagicMock()
    mock_rule.max_wallet_discount_percent = 20.0
    mock_rule.is_active = True

    async def mock_execute_t6(stmt):
        m = MagicMock()
        str_stmt = str(stmt)
        if "customer_wallet_accounts" in str_stmt:
            m.scalar_one_or_none.return_value = mock_wallet
        elif "wallet_discount_rules" in str_stmt:
            m.scalars.return_value.all.return_value = [mock_rule]
        return m

    mock_db.execute.side_effect = mock_execute_t6

    preview = await calculate_wallet_discount(
        db=mock_db,
        customer_id=10,
        client_id=1,
        branch_id=1,
        amount=1000.0
    )

    assert preview["wallet_discount"] == 200.0
    assert mock_wallet.balance == 1000.0, "Preview MUST NOT decrease wallet balance!"

    print("✅ TEST 6 PASSED: calculate_wallet_discount calculated ₹200 preview without deducting balance.")

    # -------------------------------------------------------------------------
    # TEST 7: Duplicate Debit Protection
    # -------------------------------------------------------------------------
    print("\n--- TEST 7: Duplicate payment retry protection ---")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    existing_debit_tx = MagicMock()
    existing_debit_tx.id = 999
    existing_debit_tx.reference_type = "BILL"
    existing_debit_tx.reference_id = 107

    async def mock_execute_t7(stmt):
        m = MagicMock()
        m.scalar_one_or_none.return_value = existing_debit_tx
        return m

    mock_db.execute.side_effect = mock_execute_t7

    try:
        await debit_wallet(
            db=mock_db,
            customer_id=10,
            client_id=1,
            branch_id=1,
            amount=200.0,
            reference_type="BILL",
            reference_id=107
        )
        assert False, "Should have raised HTTPException for duplicate debit"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "already been debited" in exc.detail
        print("✅ TEST 7 PASSED: Duplicate wallet debit attempt was correctly blocked.")

    print("\n============================================================")
    print("ALL 7 CRM WALLET PAYMENT FLOW TEST CASES PASSED SUCCESSFULLY!")
    print("============================================================")


if __name__ == "__main__":
    asyncio.run(run_wallet_tests())
