"""
Comprehensive Verification Tests for Multi-Tenant Loyalty Points -> Wallet Conversion Flow
"""

import sys
import os
import asyncio

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import HTTPException
from sqlalchemy import select, text
from app.db.base import *
from app.db.config import async_session
from app.accounts.branch.model import Branch
from app.accounts.customer.model import Customer
from app.accounts.crm.loyalty.model import CustomerLoyaltyAccount, LoyaltyTransaction
from app.accounts.crm.loyalty.conversion_rule.model import LoyaltyConversionRule
from app.accounts.crm.loyalty.conversion_rule.service import (
    get_active_rule,
    get_or_create_loyalty_conversion_rule,
)
from app.accounts.crm.wallet.model import CustomerWalletAccount, WalletTransaction
from app.accounts.crm.wallet.service import (
    convert_loyalty_points_to_wallet,
    get_loyalty_conversion_rule,
)


async def run_tests():
    print("=" * 70)
    print("STARTING MULTI-TENANT LOYALTY CONVERSION FLOW VERIFICATION TESTS")
    print("=" * 70)

    async with async_session() as session:

        # ---------------------------------------------------------------------
        # TEST 1: Client 1 / Branch 1 rule lookup
        # ---------------------------------------------------------------------
        print("\n--- TEST 1: Client 1 / Branch 1 rule lookup ---")
        rule1 = await get_loyalty_conversion_rule(session, client_id=1, branch_id=1)
        assert rule1 is not None, "Rule for Client 1 / Branch 1 must exist"
        assert rule1.client_id == 1 and rule1.branch_id == 1
        print("✅ TEST 1 PASSED: Correctly resolved Client 1 / Branch 1 rule.")

        # ---------------------------------------------------------------------
        # TEST 2: Client 2 / Branch 2 rule lookup
        # ---------------------------------------------------------------------
        print("\n--- TEST 2: Client 2 / Branch 2 rule lookup ---")
        rule2 = await get_loyalty_conversion_rule(session, client_id=2, branch_id=2)
        assert rule2 is not None, "Rule for Client 2 / Branch 2 must exist"
        assert rule2.client_id == 2 and rule2.branch_id == 2
        print("✅ TEST 2 PASSED: Correctly resolved Client 2 / Branch 2 rule.")

        # ---------------------------------------------------------------------
        # TEST 3: Client 4 / Branch 4 rule lookup
        # ---------------------------------------------------------------------
        print("\n--- TEST 3: Client 4 / Branch 4 rule lookup ---")
        rule4 = await get_loyalty_conversion_rule(session, client_id=4, branch_id=4)
        assert rule4 is not None, "Rule for Client 4 / Branch 4 must exist"
        assert rule4.client_id == 4 and rule4.branch_id == 4
        print("✅ TEST 3 PASSED: Correctly resolved Client 4 / Branch 4 rule.")

        # ---------------------------------------------------------------------
        # TEST 4: Client 13 / Branch 11 rule lookup (Must NOT resolve to Client 1)
        # ---------------------------------------------------------------------
        print("\n--- TEST 4: Client 13 / Branch 11 rule lookup ---")
        rule11 = await get_loyalty_conversion_rule(session, client_id=13, branch_id=11)
        assert rule11 is not None, "Rule for Client 13 / Branch 11 must exist"
        assert rule11.client_id == 13 and rule11.branch_id == 11, "Rule MUST belong to Client 13"

        wrong_rule = await get_active_rule(session, client_id=1, branch_id=11)
        assert wrong_rule is None, "Searching Client 1 for Branch 11 MUST return None"
        print("✅ TEST 4 PASSED: Branch 11 strictly mapped to Client 13, NOT Client 1.")

        # ---------------------------------------------------------------------
        # TEST 5: Cross-Client Conversion Attack Protection
        # ---------------------------------------------------------------------
        print("\n--- TEST 5: Cross-Client Conversion Attack Protection ---")
        # Try converting points for customer belonging to Client 13 using Branch 1 (which belongs to Client 1)
        # First ensure a test customer exists for Client 13
        cust_c13 = (await session.execute(
            select(Customer).where(Customer.client_id == 13)
        )).scalars().first()

        if not cust_c13:
            cust_c13 = Customer(
                name="Test Client 13 Cust",
                phone="9999913131",
                client_id=13,
                branch_id=11,
                loyalty_points=100.0,
            )
            session.add(cust_c13)
            await session.commit()
            await session.refresh(cust_c13)

        try:
            await convert_loyalty_points_to_wallet(
                session,
                customer_id=cust_c13.id,
                branch_id=1, # Branch 1 belongs to Client 1, customer belongs to Client 13!
            )
            assert False, "Cross-client conversion MUST fail!"
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "The selected branch does not belong to this customer’s client." in exc.detail
            print(f"✅ TEST 5 PASSED: Cross-client conversion blocked with detail: '{exc.detail}'")

        # ---------------------------------------------------------------------
        # TEST 6: Auto-creation of Loyalty Conversion Rule for New Branch
        # ---------------------------------------------------------------------
        print("\n--- TEST 6: Auto-creation of Loyalty Conversion Rule for New Branch ---")
        # Create temporary new branch for Client 2
        new_branch = Branch(
            name="Auto Rule Test Branch",
            address="Test Address",
            city="Test City",
            client_id=2,
            branch_code="BR999",
            status="active",
        )
        session.add(new_branch)
        await session.commit()
        await session.refresh(new_branch)

        # Call get_or_create_loyalty_conversion_rule
        new_rule = await get_or_create_loyalty_conversion_rule(
            session,
            client_id=2,
            branch_id=new_branch.id,
        )
        assert new_rule is not None
        assert new_rule.client_id == 2 and new_rule.branch_id == new_branch.id
        assert new_rule.points_required == 10.0 and new_rule.rupee_value == 5.0
        assert new_rule.is_active is True
        print(f"✅ TEST 6 PASSED: Auto-created rule (10 pts = ₹5) for Client 2 / Branch {new_branch.id}.")

        # Cleanup test branch and rule
        await session.delete(new_rule)
        await session.delete(new_branch)
        await session.commit()

        # ---------------------------------------------------------------------
        # TEST 7: Complete Loyalty-to-Wallet Conversion Flow
        # ---------------------------------------------------------------------
        print("\n--- TEST 7: Complete Loyalty-to-Wallet Conversion Flow ---")
        import time
        unique_phone = f"98{int(time.time()) % 100000000:08d}"

        # Create test customer for Client 1 / Branch 1 with 100 points
        test_cust = Customer(
            name="Loyalty Conversion Test Customer",
            phone=unique_phone,
            client_id=1,
            branch_id=1,
            loyalty_points=100.0,
        )
        session.add(test_cust)
        await session.commit()
        await session.refresh(test_cust)

        # Ensure loyalty account exists
        l_acc = CustomerLoyaltyAccount(
            customer_id=test_cust.id,
            client_id=1,
            current_points_balance=100.0,
            total_points_earned=100.0,
            total_points_redeemed=0.0,
        )
        session.add(l_acc)
        await session.commit()

        test_cust_id = test_cust.id
        l_acc_id = l_acc.id

        # Execute conversion (100 pts -> 10 pts = ₹5 => ₹50 credited)
        result = await convert_loyalty_points_to_wallet(
            session,
            customer_id=test_cust_id,
            branch_id=1,
        )

        assert result["points_converted"] == 100.0
        assert result["rupee_amount"] == 50.0
        assert result["loyalty_points_after"] == 0.0
        assert result["wallet_balance_after"] == 50.0

        # Verify DB records
        updated_l_acc = (await session.execute(
            select(CustomerLoyaltyAccount).where(CustomerLoyaltyAccount.id == l_acc_id)
        )).scalar_one()
        assert updated_l_acc.current_points_balance == 0.0

        # Verify transactions created
        loyalty_tx = (await session.execute(
            select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id == test_cust_id)
        )).scalars().all()
        assert len(loyalty_tx) == 1
        assert loyalty_tx[0].transaction_type == "CONVERSION"
        assert loyalty_tx[0].points == -100.0

        wallet_tx = (await session.execute(
            select(WalletTransaction).where(WalletTransaction.customer_id == test_cust_id)
        )).scalars().all()
        assert len(wallet_tx) == 1
        assert wallet_tx[0].transaction_type == "CREDIT"
        assert wallet_tx[0].amount == 50.0
        assert wallet_tx[0].reference_type == "LOYALTY_CONVERSION"
        print(f"✅ TEST 7 PASSED: Converted 100 loyalty points into ₹50 wallet credit successfully.")

        # ---------------------------------------------------------------------
        # TEST 8: Zero Loyalty Points Conversion Attempt
        # ---------------------------------------------------------------------
        print("\n--- TEST 8: Zero Loyalty Points Conversion Attempt ---")
        try:
            await convert_loyalty_points_to_wallet(
                session,
                customer_id=test_cust_id,
                branch_id=1,
            )
            assert False, "Converting 0 loyalty points MUST fail!"
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "No loyalty points available for conversion" in exc.detail
            print(f"✅ TEST 8 PASSED: Prevented conversion when points are 0 ('{exc.detail}').")

        # Cleanup test records
        for wtx in wallet_tx:
            await session.delete(wtx)
        for ltx in loyalty_tx:
            await session.delete(ltx)
        w_acc = (await session.execute(
            select(CustomerWalletAccount).where(CustomerWalletAccount.customer_id == test_cust_id)
        )).scalars().first()
        if w_acc:
            await session.delete(w_acc)
        del_l_acc = (await session.execute(
            select(CustomerLoyaltyAccount).where(CustomerLoyaltyAccount.id == l_acc_id)
        )).scalars().first()
        if del_l_acc:
            await session.delete(del_l_acc)
        del_cust = (await session.execute(
            select(Customer).where(Customer.id == test_cust_id)
        )).scalars().first()
        if del_cust:
            await session.delete(del_cust)
        await session.commit()

        print("\n" + "=" * 70)
        print("ALL 8 MULTI-TENANT LOYALTY CONVERSION FLOW TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_tests())
