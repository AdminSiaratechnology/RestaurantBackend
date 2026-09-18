import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import asyncio
import secrets
from unittest.mock import MagicMock, patch

from sqlalchemy import delete
from app.db.base import Base
from app.db.config import engine, async_session
from app.accounts.enum import UserRole
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.branch.model import Branch, statusEnum as BranchStatus
from app.accounts.table.model import Table, TableStatus
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.customer.model import Customer
from app.accounts.order.model import Order, OrderItem
from app.accounts.bill.model import Bill
from app.accounts.payment.model import Payment
from app.accounts.table_qr.model import TableQRCode, RestaurantSession
from app.accounts.table_qr.service import TableQRService, PublicCustomerQRService, hash_token
from app.accounts.table_qr.schema import (
    SessionCustomerAttachReq,
    PublicOrderCreateReq,
    PublicOrderItemReq,
    RazorpayPaymentVerifyReq,
)

async def run_all_tests():
    print("Starting QR End-to-End System Tests...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db_session:
        # Generate unique test email/slug to avoid unique constraint collisions
        suffix = secrets.token_hex(4)
        
        partner = Partner(
            name="Test Partner",
            email=f"partner_{suffix}@example.com",
            password_hash="hashed_pw",
        )
        db_session.add(partner)
        await db_session.flush()

        client = Client(
            partner_id=partner.id,
            name="Test Client",
            email=f"client_{suffix}@example.com",
            password_hash="hashed_pw",
            slug=f"client-{suffix}",
        )
        db_session.add(client)
        await db_session.flush()

        branch = Branch(
            client_id=client.id,
            name="Main Branch",
            address="123 St",
            city="City",
            country="India",
            state="State",
            pincode="123456",
            currency="INR",
            decimal_places=2,
            tax_type="GST",
            branch_code=f"BR-{suffix[:6].upper()}",
            status=BranchStatus.ACTIVE,
        )
        db_session.add(branch)
        await db_session.flush()

        table = Table(
            client_id=client.id,
            branch_id=branch.id,
            name="Table 1",
            number_of_seats=4,
            status=TableStatus.available,
            is_active=True,
        )
        db_session.add(table)
        await db_session.flush()

        item = Item(
            client_id=client.id,
            branch_id=branch.id,
            name="Special Biryani",
            is_active=True,
        )
        db_session.add(item)
        await db_session.flush()

        pricing = Pricing(
            client_id=client.id,
            branch_id=branch.id,
            item_id=item.id,
            price=300.0,
            discount=0.0,
            tax=5.0,
            tax_type="GST",
            is_active=True,
        )
        db_session.add(pricing)
        await db_session.commit()

        user = MagicMock(id=client.id, client_id=client.id)
        role = UserRole.CLIENT

        # Test 1: Staff QR Generation
        qr_res = await TableQRService.generate_qr(db_session, table_id=table.id, user=user, role=role)
        print("✅ QR Generation passed:", qr_res["qr_token"][:10] + "...")
        assert qr_res["table_id"] == table.id
        assert qr_res["is_active"] is True

        # Test 2: Verify Token Hashing Security
        db_qr = await db_session.get(TableQRCode, qr_res["id"])
        assert db_qr.token_hash == hash_token(qr_res["qr_token"])
        print("✅ Token SHA-256 hash security verified")

        # Test 3: Public QR Resolution & Session Creation
        resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
        assert resolve_res["branch_name"] == "Main Branch"
        assert resolve_res["table_name"] == "Table 1"
        print("✅ Public QR Resolution passed. Session Token created.")

        session_token = resolve_res["session_token"]
        session = await PublicCustomerQRService.get_session_by_token(db_session, session_token)
        assert session.table_id == table.id

        # Test 4: Customer Identification & Session Attachment
        attach_req = SessionCustomerAttachReq(name="Jane Doe", phone=f"987{secrets.token_hex(3)}", email=f"jane_{suffix}@example.com")
        cust_res = await PublicCustomerQRService.attach_customer(db_session, session, attach_req)
        assert cust_res["name"] == "Jane Doe"
        print("✅ Customer attached to session successfully")

        # Test 5: Public Branch-Isolated Menu
        menu = await PublicCustomerQRService.get_public_menu(db_session, session)
        assert len(menu) > 0
        print("✅ Public branch menu loaded successfully")

        # Test 6: Secure QR Order Creation with Server-Side Recalculation
        order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=item.id, quantity=2)], notes="Less spicy")
        order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
        assert order.table_id == table.id
        assert order.status == "pending"
        assert len(order.order_items) == 1
        assert order.order_items[0].item_id == item.id
        assert order.order_items[0].quantity == 2
        print("✅ Secure QR Order created successfully. Total:", order.total_amount)

        # Verify route items DTO mapping executes without lazy-loading / MissingGreenlet
        items_dto = [
            {
                "id": oi.id,
                "item_id": oi.item_id,
                "quantity": oi.quantity,
                "unit_price": oi.unit_price,
                "total_price": oi.total_price,
                "order_status": oi.order_status,
            }
            for oi in order.order_items
        ]
        assert len(items_dto) == 1
        print("✅ Route DTO serialization verified without MissingGreenlet error")

        # Verify Table marked occupied
        updated_table = await db_session.get(Table, table.id)
        assert updated_table.status == TableStatus.occupied
        print("✅ Table status updated to 'occupied'")

        # Test 7: Payment Initiation
        with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp_init:
            mock_rzp_init.return_value = {"id": f"order_mock_{suffix}", "amount": 63000, "currency": "INR"}
            init_res = await PublicCustomerQRService.initiate_payment(db_session, session, order.id)
            assert init_res["bill_id"] is not None
            print("✅ Payment initiated. Razorpay order_id:", init_res["razorpay_order_id"])

        # Test 8: Atomic & Idempotent Razorpay Verification
        with patch("app.accounts.table_qr.service.verify_razorpay_payment") as mock_rzp_verify:
            mock_rzp_verify.return_value = None
            verify_req = RazorpayPaymentVerifyReq(
                bill_id=init_res["bill_id"],
                razorpay_order_id=f"order_mock_{suffix}",
                razorpay_payment_id=f"pay_mock_{suffix}",
                razorpay_signature=f"sig_mock_{suffix}"
            )

            res1 = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
            assert res1["status"] == "success"
            assert res1["order_status"] == "confirmed"
            print("✅ Initial payment verification passed. Order confirmed.")

            # Duplicate call (idempotency check)
            res2 = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
            assert res2["status"] == "success"
            assert res2["order_status"] == "confirmed"
            print("✅ Idempotent repeated payment verification passed.")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
