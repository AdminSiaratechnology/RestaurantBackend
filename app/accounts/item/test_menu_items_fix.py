"""
Verification Test for Menu Items Fix for Branch 18 & Cache Invalidation
"""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir in sys.path:
    sys.path.remove(script_dir)

backend_dir = os.path.abspath(os.path.join(script_dir, "../../.."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import asyncio
import json

from sqlalchemy import select
from app.db.base import *
from app.db.config import async_session
from app.accounts.item.service import get_items_service, create_item_service, delete_item_service
from app.accounts.order.router import get_menu
from app.accounts.item.schema import ItemCreate
from app.core.cache import Cache


class DummyUser:
    id = 14
    client_id = 14
    branch_id = 18
    selected_branch_id = 18


async def run_tests():
    print("=" * 70)
    print("STARTING MENU ITEMS FIX & CACHE INVALIDATION VERIFICATION TESTS")
    print("=" * 70)

    async with async_session() as session:
        current = {"role": "client", "user": DummyUser()}

        # ---------------------------------------------------------------------
        # TEST 1: Verify get_items_service returns all 7 items for branch 18
        # ---------------------------------------------------------------------
        print("\n--- TEST 1: Verify get_items_service for branch 18 ---")
        items = await get_items_service(
            db=session,
            current=current,
            branch_id=18,
        )
        item_ids = [item.id for item in items]
        print(f"Items returned by get_items_service: {len(items)} (IDs: {item_ids})")
        assert len(items) == 7, f"Expected 7 items, got {len(items)}"
        for expected_id in [607, 608, 609, 610, 611, 612, 613]:
            assert expected_id in item_ids, f"Item {expected_id} missing from get_items_service!"
        print("✅ TEST 1 PASSED: get_items_service returns all 7 active items with pricing.")

        # ---------------------------------------------------------------------
        # TEST 2: Verify get_menu (/order/menu) returns all 7 items for branch 18
        # ---------------------------------------------------------------------
        print("\n--- TEST 2: Verify get_menu (/order/menu) for branch 18 ---")
        menu_response = await get_menu(
            db=session,
            client_id=14,
            branch_id=18,
            current=current,
        )
        print("Menu Response Categories:", list(menu_response.keys()))
        aasf_items = menu_response.get("aasf", [])
        aasf_ids = [i["id"] for i in aasf_items]
        print(f"Category 'aasf' items count: {len(aasf_items)} (IDs: {aasf_ids})")
        assert len(aasf_items) == 7, f"Expected 7 items in category 'aasf', got {len(aasf_items)}"
        for expected_id in [607, 608, 609, 610, 611, 612, 613]:
            assert expected_id in aasf_ids, f"Item {expected_id} missing from category 'aasf' in menu!"
        print("✅ TEST 2 PASSED: /order/menu returns all 7 items in category 'aasf'.")

        # ---------------------------------------------------------------------
        # TEST 3: Verify Cache Invalidation on Item Creation & Deletion
        # ---------------------------------------------------------------------
        print("\n--- TEST 3: Verify Cache Invalidation on Item Creation & Deletion ---")
        # Create a temp item
        payload = ItemCreate(
            name="Temp Verification Test Item",
            category_id=104,
            price=999.0,
            is_active=True,
        )
        created_item = await create_item_service(
            payload=payload,
            db=session,
            current=current,
            branch_id=18,
            client_id=14,
        )
        print(f"Created temp item ID: {created_item.id}")

        # Fetch menu again (should now return 8 items due to cache invalidation)
        menu_response_after_create = await get_menu(
            db=session,
            client_id=14,
            branch_id=18,
            current=current,
        )
        aasf_items_after_create = menu_response_after_create.get("aasf", [])
        print(f"Category 'aasf' items count after creation: {len(aasf_items_after_create)}")
        assert len(aasf_items_after_create) == 8, f"Expected 8 items after creation, got {len(aasf_items_after_create)}"

        # Delete temp item
        await delete_item_service(
            item_id=created_item.id,
            db=session,
            current=current,
        )
        print(f"Deleted temp item ID: {created_item.id}")

        # Fetch menu again (should revert to 7 items due to cache invalidation)
        menu_response_after_delete = await get_menu(
            db=session,
            client_id=14,
            branch_id=18,
            current=current,
        )
        aasf_items_after_delete = menu_response_after_delete.get("aasf", [])
        print(f"Category 'aasf' items count after deletion: {len(aasf_items_after_delete)}")
        assert len(aasf_items_after_delete) == 7, f"Expected 7 items after deletion, got {len(aasf_items_after_delete)}"
        print("✅ TEST 3 PASSED: Automatic cache invalidation works cleanly on item creation and deletion.")

        print("\n" + "=" * 70)
        print("ALL MENU ITEMS FIX & CACHE INVALIDATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_tests())
