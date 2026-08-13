"""
app/accounts/crm/test_loyalty_redemption_rules.py

Unit tests verifying that redeeming loyalty points NEVER changes customer rank or spend,
testing all required test cases.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import app.db.base  # Register Base models first
from app.accounts.customer.model import Customer
from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.crm.loyalty.model import CustomerLoyaltyAccount, LoyaltyTransaction
from app.accounts.crm.loyalty.service import (
    calculate_customer_rank,
    redeem_loyalty_points,
    convert_current_spend_to_loyalty_points,
)


class TestLoyaltyRedemptionRules(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Mock active branch rank rule (Bronze: 0-5000, Silver: 5000-10000, Gold: 10000+)
        self.rank_rule = CRMBranchRankRule(
            id=1,
            client_id=10,
            branch_id=100,
            bronze_min=0.0,
            silver_min=5000.0,
            gold_min=10000.0,
            bronze_pts=1.0,
            silver_pts=2.0,
            gold_pts=3.0,
            is_active=True,
        )

    async def test_case_1_silver_customer_redeems_points(self):
        """
        Case 1: Silver customer (total_spend=8000, rank=Silver, points=160).
        Redeem 100 points.
        Expected: total_spend=8000, rank=Silver, points_balance=60.
        """
        customer = Customer(
            id=1,
            client_id=10,
            branch_id=100,
            name="Test Silver",
            total_spend=8000.0,
            current_spend=8000.0,
            current_rank="Silver",
            loyalty_points=160.0,
        )

        account = CustomerLoyaltyAccount(
            id=1,
            customer_id=1,
            client_id=10,
            total_points_earned=160.0,
            total_points_redeemed=0.0,
            current_points_balance=160.0,
            converted_spend=8000.0,
        )

        db = AsyncMock()

        async def mock_get(entity, entity_id):
            if entity == Customer and entity_id == 1:
                return customer
            return None

        async def mock_execute(stmt):
            mock_res = MagicMock()
            # If querying rank rule or loyalty account
            stmt_str = str(stmt)
            if "customer_loyalty_accounts" in stmt_str:
                mock_res.scalar_one_or_none.return_value = account
            elif "crm_branch_rank_rules" in stmt_str:
                mock_res.scalars.return_value.first.return_value = self.rank_rule
            return mock_res

        db.get.side_effect = mock_get
        db.execute.side_effect = mock_execute
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Redeem 100 points
        res = await redeem_loyalty_points(
            db=db,
            customer_id=1,
            points_to_redeem=100.0,
            description="Test Redemption 100 pts",
        )

        # Assertions
        self.assertEqual(customer.total_spend, 8000.0)
        self.assertEqual(customer.current_spend, 0.0)
        self.assertEqual(customer.current_rank, "Silver")
        self.assertEqual(account.total_points_redeemed, 100.0)
        self.assertEqual(account.current_points_balance, 60.0)
        self.assertEqual(customer.loyalty_points, 60.0)

        # Recalculate rank after redemption to verify rank remains Silver and current_spend remains 0
        rank = await calculate_customer_rank(db=db, customer=customer, branch_id=100)
        self.assertEqual(rank, "Silver")
        self.assertEqual(customer.current_rank, "Silver")
        self.assertEqual(customer.total_spend, 8000.0)
        self.assertEqual(customer.current_spend, 0.0)

    async def test_case_2_gold_customer_redeems_all_points(self):
        """
        Case 2: Gold customer (total_spend=15000, rank=Gold, points=500).
        Redeem 500 points.
        Expected: total_spend=15000, rank=Gold, points_balance=0, current_spend=0.
        """
        customer = Customer(
            id=2,
            client_id=10,
            branch_id=100,
            name="Test Gold",
            total_spend=15000.0,
            current_spend=15000.0,
            current_rank="Gold",
            loyalty_points=500.0,
        )

        account = CustomerLoyaltyAccount(
            id=2,
            customer_id=2,
            client_id=10,
            total_points_earned=500.0,
            total_points_redeemed=0.0,
            current_points_balance=500.0,
            converted_spend=15000.0,
        )

        db = AsyncMock()

        async def mock_get(entity, entity_id):
            if entity == Customer and entity_id == 2:
                return customer
            return None

        async def mock_execute(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt)
            if "customer_loyalty_accounts" in stmt_str:
                mock_res.scalar_one_or_none.return_value = account
            elif "crm_branch_rank_rules" in stmt_str:
                mock_res.scalars.return_value.first.return_value = self.rank_rule
            return mock_res

        db.get.side_effect = mock_get
        db.execute.side_effect = mock_execute
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Redeem 500 points
        res = await redeem_loyalty_points(
            db=db,
            customer_id=2,
            points_to_redeem=500.0,
            description="Redeem all points",
        )

        # Assertions
        self.assertEqual(customer.total_spend, 15000.0)
        self.assertEqual(customer.current_spend, 0.0)
        self.assertEqual(customer.current_rank, "Gold")
        self.assertEqual(account.total_points_redeemed, 500.0)
        self.assertEqual(account.current_points_balance, 0.0)
        self.assertEqual(customer.loyalty_points, 0.0)

        # Recalculate rank after redemption to verify rank remains Gold
        rank = await calculate_customer_rank(db=db, customer=customer, branch_id=100)
        self.assertEqual(rank, "Gold")
        self.assertEqual(customer.current_rank, "Gold")

    async def test_case_3_bronze_customer_redeems_points(self):
        """
        Case 3: Bronze customer (total_spend=3000, rank=Bronze, points=30).
        Redeem 20 points.
        Expected: total_spend=3000, rank=Bronze, points_balance=10, current_spend=0.
        """
        customer = Customer(
            id=3,
            client_id=10,
            branch_id=100,
            name="Test Bronze",
            total_spend=3000.0,
            current_spend=3000.0,
            current_rank="Bronze",
            loyalty_points=30.0,
        )

        account = CustomerLoyaltyAccount(
            id=3,
            customer_id=3,
            client_id=10,
            total_points_earned=30.0,
            total_points_redeemed=0.0,
            current_points_balance=30.0,
            converted_spend=3000.0,
        )

        db = AsyncMock()

        async def mock_get(entity, entity_id):
            if entity == Customer and entity_id == 3:
                return customer
            return None

        async def mock_execute(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt)
            if "customer_loyalty_accounts" in stmt_str:
                mock_res.scalar_one_or_none.return_value = account
            elif "crm_branch_rank_rules" in stmt_str:
                mock_res.scalars.return_value.first.return_value = self.rank_rule
            return mock_res

        db.get.side_effect = mock_get
        db.execute.side_effect = mock_execute
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Redeem 20 points
        res = await redeem_loyalty_points(
            db=db,
            customer_id=3,
            points_to_redeem=20.0,
        )

        # Assertions
        self.assertEqual(customer.total_spend, 3000.0)
        self.assertEqual(customer.current_spend, 0.0)
        self.assertEqual(customer.current_rank, "Bronze")
        self.assertEqual(account.total_points_redeemed, 20.0)
        self.assertEqual(account.current_points_balance, 10.0)
        self.assertEqual(customer.loyalty_points, 10.0)

        # Recalculate rank after redemption
        rank = await calculate_customer_rank(db=db, customer=customer, branch_id=100)
        self.assertEqual(rank, "Bronze")

    async def test_current_spend_redemption_cycle_and_post_redemption_orders(self):
        """
        Test complete redemption cycle:
        1. Before redemption: total_spend=8000, current_spend=8000
        2. Successful redemption: current_spend resets to 0.0, total_spend stays 8000
        3. New order 2000: current_spend accumulates to 2000, total_spend becomes 10000
        4. Next order 1500: current_spend accumulates to 3500, total_spend becomes 11500
        """
        from app.accounts.crm.customer_history.service import update_customer_stats
        from app.accounts.crm.customer_history.model import CustomerVisitHistory

        customer = Customer(
            id=5,
            client_id=10,
            branch_id=100,
            name="Cycle Test Customer",
            total_spend=8000.0,
            current_spend=8000.0,
            current_rank="Silver",
            loyalty_points=160.0,
            total_orders=4,
            total_visits=4,
        )

        account = CustomerLoyaltyAccount(
            id=5,
            customer_id=5,
            client_id=10,
            total_points_earned=160.0,
            total_points_redeemed=0.0,
            current_points_balance=160.0,
            converted_spend=8000.0,
        )

        db = AsyncMock()

        async def mock_get(entity, entity_id):
            if entity == Customer and entity_id == 5:
                return customer
            return None

        async def mock_execute(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt)
            if "customer_loyalty_accounts" in stmt_str:
                mock_res.scalar_one_or_none.return_value = account
            elif "crm_branch_rank_rules" in stmt_str:
                mock_res.scalars.return_value.first.return_value = self.rank_rule
            return mock_res

        db.get.side_effect = mock_get
        db.execute.side_effect = mock_execute
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Step 1: Perform Redemption
        res = await redeem_loyalty_points(db=db, customer_id=5, points_to_redeem=100.0)
        self.assertEqual(customer.current_spend, 0.0)
        self.assertEqual(customer.total_spend, 8000.0)

        # Step 2: New Order ₹2,000
        visit1 = CustomerVisitHistory(id=101, customer_id=5, total_amount=2000.0)
        await update_customer_stats(db=db, customer=customer, visit=visit1)

        self.assertEqual(customer.current_spend, 2000.0)
        self.assertEqual(customer.total_spend, 10000.0)
        self.assertEqual(visit1.current_spend, 2000.0)

        # Step 3: Next Order ₹1,500
        visit2 = CustomerVisitHistory(id=102, customer_id=5, total_amount=1500.0)
        await update_customer_stats(db=db, customer=customer, visit=visit2)

        self.assertEqual(customer.current_spend, 3500.0)
        self.assertEqual(customer.total_spend, 11500.0)
        self.assertEqual(visit2.current_spend, 3500.0)

        # Verify old visit snapshot remains 2000
        self.assertEqual(visit1.current_spend, 2000.0)

    async def test_conversion_uses_dynamic_crm_branch_rank_rule(self):
        """
        Verify that convert_current_spend_to_loyalty_points dynamically uses the exact points_per_100
        configured in CRMBranchRankRule for the customer's branch.
        """
        custom_rule = CRMBranchRankRule(
            id=2,
            client_id=10,
            branch_id=100,
            bronze_min=0.0,
            silver_min=5000.0,
            gold_min=10000.0,
            bronze_pts=1.0,
            silver_pts=5.0,
            gold_pts=10.0,
            is_active=True,
        )

        customer = Customer(
            id=4,
            client_id=10,
            branch_id=100,
            name="Test Silver Custom Rule",
            total_spend=7000.0,
            current_spend=7000.0,
            current_rank="Silver",
            loyalty_points=0.0,
        )

        account = CustomerLoyaltyAccount(
            id=4,
            customer_id=4,
            client_id=10,
            total_points_earned=0.0,
            total_points_redeemed=0.0,
            current_points_balance=0.0,
            converted_spend=0.0,
        )

        db = AsyncMock()

        async def mock_get(entity, entity_id):
            if entity == Customer and entity_id == 4:
                return customer
            return None

        async def mock_execute(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt)
            if "customer_loyalty_accounts" in stmt_str:
                mock_res.scalar_one_or_none.return_value = account
            elif "crm_branch_rank_rules" in stmt_str:
                mock_res.scalars.return_value.first.return_value = custom_rule
            elif "customer_visit_history" in stmt_str:
                mock_res.scalar_one_or_none.return_value = None
            return mock_res

        db.get.side_effect = mock_get
        db.execute.side_effect = mock_execute
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Convert ₹7,000 eligible spend at Silver rate (5 pts per 100)
        res = await convert_current_spend_to_loyalty_points(db=db, customer_id=4)

        # Expected: 7000 / 100 * 5 = 350 points
        self.assertEqual(res["points_per_100"], 5.0)
        self.assertEqual(res["points_earned"], 350.0)
        self.assertEqual(res["current_points_balance"], 350.0)
        self.assertEqual(customer.current_rank, "Silver")
        self.assertEqual(customer.total_spend, 7000.0)
        self.assertEqual(customer.current_spend, 0.0)

        # Verify REDEEM transaction added
        added_objs = [call[0][0] for call in db.add.call_args_list]
        tx = next(obj for obj in added_objs if isinstance(obj, LoyaltyTransaction))
        self.assertEqual(tx.transaction_type, "REDEEM")
        self.assertEqual(tx.points, 350.0)

    async def test_conversion_zero_current_spend_raises_http_exception(self):
        """
        Verify that attempting to convert current spend when current_spend is 0.0 raises 400.
        """
        from fastapi import HTTPException

        customer = Customer(
            id=6,
            client_id=10,
            branch_id=100,
            name="Zero Spend Customer",
            total_spend=5000.0,
            current_spend=0.0,
            current_rank="Silver",
            loyalty_points=100.0,
        )

        db = AsyncMock()

        async def mock_get(entity, entity_id):
            if entity == Customer and entity_id == 6:
                return customer
            return None

        db.get.side_effect = mock_get

        with self.assertRaises(HTTPException) as ctx:
            await convert_current_spend_to_loyalty_points(db=db, customer_id=6)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("no current spend", ctx.exception.detail)
        self.assertEqual(customer.current_spend, 0.0)
        self.assertEqual(customer.total_spend, 5000.0)


if __name__ == "__main__":
    unittest.main()



