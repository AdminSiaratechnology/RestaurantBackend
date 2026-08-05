"""
app/accounts/crm/test_rank_rules.py

Comprehensive test suite for Branch-wise Customer Rank Rule Management.
Tests threshold range validation, auth dictionary handling, repository/service operations,
and RankHandler dynamic evaluation across different branch rules.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import app.db.base  # noqa
from app.accounts.crm.rank_rules.schema import RankRuleBase
from app.accounts.crm.rank_rules.service import _extract_client_id
from app.accounts.crm.handlers.rank import RankHandler
from app.accounts.crm.handlers.base import CRMContext
from app.accounts.crm.events.schema import BillCompletedEvent
from app.accounts.crm.utils.logger import crm_logger
from app.accounts.enum import UserRole


async def test_threshold_validations():
    crm_logger.info("=== 1. Testing Threshold Range Validation ===")

    # Test 1a: Valid thresholds (Branch A: 0-4999, 5000-14999, 15000+)
    valid_rule = RankRuleBase(
        bronze_min=0.0,
        bronze_max=4999.0,
        silver_min=4999.0,
        silver_max=14999.0,
        gold_min=14999.0,
    )
    assert valid_rule.bronze_min == 0.0
    crm_logger.info("[Test 1a Passed] Valid threshold configuration accepted.")

    # Test 1b: Reject bronze_min != 0
    try:
        RankRuleBase(
            bronze_min=100.0,
            bronze_max=4999.0,
            silver_min=4999.0,
            silver_max=14999.0,
            gold_min=14999.0,
        )
        assert False, "Should have raised ValueError for bronze_min != 0"
    except ValueError as val_err:
        crm_logger.info(f"[Test 1b Passed] Rejected non-zero bronze_min: {val_err}")

    # Test 1c: Reject overlapping ranges (Bronze 0-10000, Silver 8000-20000)
    try:
        RankRuleBase(
            bronze_min=0.0,
            bronze_max=10000.0,
            silver_min=8000.0,
            silver_max=20000.0,
            gold_min=20000.0,
        )
        assert False, "Should have raised ValueError for overlapping silver_min"
    except ValueError as val_err:
        crm_logger.info(f"[Test 1c Passed] Rejected overlapping ranges: {val_err}")

    # Test 1d: Reject gapped ranges (Bronze 0-10000, Silver 12000-20000)
    try:
        RankRuleBase(
            bronze_min=0.0,
            bronze_max=10000.0,
            silver_min=12000.0,
            silver_max=20000.0,
            gold_min=20000.0,
        )
        assert False, "Should have raised ValueError for gapped silver_min"
    except ValueError as val_err:
        crm_logger.info(f"[Test 1d Passed] Rejected gapped ranges: {val_err}")


async def test_auth_extraction():
    crm_logger.info("\n=== 2. Testing Auth Response Handling (dict: {'user': user, 'role': role}) ===")

    mock_client = MagicMock()
    mock_client.id = 42

    mock_staff = MagicMock()
    mock_staff.client_id = 99

    client_context = {"user": mock_client, "role": UserRole.CLIENT}
    staff_context = {"user": mock_staff, "role": UserRole.STAFF}

    assert _extract_client_id(client_context) == 42
    crm_logger.info("[Test 2a Passed] Client role correctly extracted user.id (42).")

    assert _extract_client_id(staff_context) == 99
    crm_logger.info("[Test 2b Passed] Staff role correctly extracted user.client_id (99).")


async def test_rank_handler_branch_wise_eval():
    crm_logger.info("\n=== 3. Testing RankHandler Branch-wise Evaluation ===")

    handler = RankHandler()

    # Create mock branch rules
    rule_branch_1 = MagicMock()
    rule_branch_1.branch_id = 1
    rule_branch_1.bronze_min = 0.0
    rule_branch_1.bronze_max = 4999.0
    rule_branch_1.silver_min = 4999.0
    rule_branch_1.silver_max = 14999.0
    rule_branch_1.gold_min = 14999.0
    rule_branch_1.is_active = True

    rule_branch_2 = MagicMock()
    rule_branch_2.branch_id = 2
    rule_branch_2.bronze_min = 0.0
    rule_branch_2.bronze_max = 9999.0
    rule_branch_2.silver_min = 9999.0
    rule_branch_2.silver_max = 24999.0
    rule_branch_2.gold_min = 24999.0
    rule_branch_2.is_active = True

    # Test Case A: Customer at Branch 1 with ₹7,500 spend -> Silver
    mock_db1 = AsyncMock()
    res1 = MagicMock()
    res1.scalars.return_value.first.return_value = rule_branch_1
    mock_db1.execute.return_value = res1

    customer_b1 = MagicMock()
    customer_b1.id = 101
    customer_b1.branch_id = 1
    customer_b1.total_spend = 7500.0
    customer_b1.current_rank = "Bronze"

    event = BillCompletedEvent(
        event="bill_completed",
        bill_id=1,
        order_id=1,
        customer_id=101,
        client_id=1,
        branch_id=1,
    )
    context1 = CRMContext(event=event, db=mock_db1, customer=customer_b1)

    await handler.process(context1)
    assert context1.dto.new_rank == "Silver"
    crm_logger.info(
        "[Test 3a Passed] Branch 1 Customer (Spend ₹7,500) correctly evaluated as Silver."
    )

    # Test Case B: Customer at Branch 2 with ₹7,500 spend -> Bronze
    mock_db2 = AsyncMock()
    res2 = MagicMock()
    res2.scalars.return_value.first.return_value = rule_branch_2
    mock_db2.execute.return_value = res2

    customer_b2 = MagicMock()
    customer_b2.id = 102
    customer_b2.branch_id = 2
    customer_b2.total_spend = 7500.0
    customer_b2.current_rank = "Bronze"

    context2 = CRMContext(event=event, db=mock_db2, customer=customer_b2)

    await handler.process(context2)
    assert context2.dto.new_rank == "Bronze"
    crm_logger.info(
        "[Test 3b Passed] Branch 2 Customer (Spend ₹7,500) correctly evaluated as Bronze."
    )

    # Test Case C: Customer at Branch 3 with NO active rule -> Graceful Skip
    mock_db3 = AsyncMock()
    res3 = MagicMock()
    res3.scalars.return_value.first.return_value = None
    mock_db3.execute.return_value = res3

    customer_b3 = MagicMock()
    customer_b3.id = 103
    customer_b3.branch_id = 3
    customer_b3.total_spend = 7500.0
    customer_b3.current_rank = "Bronze"

    context3 = CRMContext(event=event, db=mock_db3, customer=customer_b3)

    await handler.process(context3)
    assert context3.dto.new_rank == "Bronze"
    crm_logger.info(
        "[Test 3c Passed] Branch 3 Customer (No Rule) gracefully skipped without crashing."
    )

    crm_logger.info("\n=== ALL BRANCH RANK RULE TESTS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(test_threshold_validations())
    asyncio.run(test_auth_extraction())
    asyncio.run(test_rank_handler_branch_wise_eval())
