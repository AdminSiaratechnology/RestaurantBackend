"""
app/accounts/crm/test_crm_module.py

Verification script for the CRM Background Processing Module.
Tests event validation, dispatcher registration, handler execution, and mock end-to-end pipeline.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

# Pre-register ORM models via app.db.base
import app.db.base  # noqa

from app.accounts.crm.config import crm_config
from app.accounts.crm.events.dispatcher import CRMEventDispatcher
from app.accounts.crm.events.publisher import CRMEventPublisher
from app.accounts.crm.handlers.base import CRMContext
from app.accounts.crm.events.schema import BillCompletedEvent
from app.accounts.crm.utils.logger import crm_logger


async def test_crm_pipeline():
    crm_logger.info("=== Running CRM Module Verification Test ===")

    # 1. Test Event Payload Validation
    event_data = {
        "event": "bill_completed",
        "bill_id": 125,
        "order_id": 98,
        "customer_id": 9,
        "client_id": 1,
        "branch_id": 1
    }
    event = BillCompletedEvent(**event_data)
    assert event.bill_id == 125
    assert event.customer_id == 9
    crm_logger.info("[Test 1 PASSED] BillCompletedEvent Pydantic schema validation successful.")

    # 2. Test Dispatcher Pipeline Assembly
    dispatcher = CRMEventDispatcher()
    assert len(dispatcher.handlers) == 8
    handler_names = [h.name for h in dispatcher.handlers]
    crm_logger.info(f"[Test 2 PASSED] Dispatcher loaded 8 handlers: {handler_names}")

    # 3. Test Mock Context Execution
    mock_db = AsyncMock()
    mock_offer = MagicMock()
    mock_offer.id = 1
    mock_offer.offer_name = "WELCOME_SILVER"
    mock_offer.gold_min = 14999.0
    mock_offer.silver_min = 4999.0

    mock_rule = MagicMock()
    mock_rule.bronze_min = 0.0
    mock_rule.bronze_max = 4999.0
    mock_rule.silver_min = 4999.0
    mock_rule.silver_max = 14999.0
    mock_rule.gold_min = 14999.0

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_offer
    mock_result.scalars.return_value.first.return_value = mock_rule
    mock_db.execute.return_value = mock_result
    mock_db.flush.return_value = None
    mock_db.add.return_value = None

    # Mock Customer model
    mock_customer = MagicMock()
    mock_customer.id = 9
    mock_customer.name = "John Doe"
    mock_customer.phone = "+919876543210"
    mock_customer.total_visits = 4
    mock_customer.total_spend = 4500
    mock_customer.total_orders = 4
    mock_customer.current_rank = "Bronze"
    mock_customer.dob = None
    mock_customer.anniversary = None
    mock_customer.birthday_wish_sent = False
    mock_customer.anniversary_wish_sent = False
    mock_customer.preferred_contact = "WhatsApp"

    # Mock Bill model
    mock_bill = MagicMock()
    mock_bill.id = 125
    mock_bill.grand_total = 1000.0
    mock_bill.discount_amount = 0.0
    mock_bill.tax_total = 50.0
    mock_bill.payment_method = "UPI"
    mock_bill.order_type = "Dine-In"
    mock_bill.billed_at = None

    context = CRMContext(
        event=event,
        db=mock_db,
        bill=mock_bill,
        customer=mock_customer,
        order=MagicMock()
    )

    # Run dispatcher pipeline with mock context
    for handler in dispatcher.handlers:
        await handler.process(context)

    # Assertions after execution
    assert mock_customer.total_visits == 5
    assert mock_customer.total_spend == 5500
    assert context.dto.new_rank == "Silver"
    assert context.dto.rank_upgraded is True
    assert context.dto.points_earned == 10.0
    assert len(context.dto.coupons_issued) == 1
    crm_logger.info(
        f"[Test 3 PASSED] Pipeline executed successfully! "
        f"New Rank: {context.dto.new_rank}, Points: {context.dto.points_earned}, Coupons: {context.dto.coupons_issued}"
    )

    crm_logger.info("=== ALL CRM MODULE TESTS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(test_crm_pipeline())
