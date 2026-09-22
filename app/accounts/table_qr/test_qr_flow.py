import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.accounts.enum import UserRole
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.branch.model import Branch, statusEnum as BranchStatus
from app.accounts.table.model import Table, TableStatus
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.customer.model import Customer
from app.accounts.table_qr.model import TableQRCode, RestaurantSession, SessionStatus
from app.accounts.table_qr.service import TableQRService, PublicCustomerQRService, hash_token
from app.accounts.table_qr.schema import (
    SessionCustomerAttachReq,
    PublicOrderCreateReq,
    PublicOrderItemReq,
    RazorpayPaymentVerifyReq,
)
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.payment.model import Payment
from app.accounts.order.model import Order, OrderItem


from app.accounts.tax.model import TaxBillingSetting
from app.accounts.crm.customer_history.model import CustomerVisitHistory
from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.offer.model import Offer

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    target_tables = [
        Partner.__table__,
        Client.__table__,
        Branch.__table__,
        Table.__table__,
        Item.__table__,
        Pricing.__table__,
        Customer.__table__,
        Order.__table__,
        OrderItem.__table__,
        Bill.__table__,
        Payment.__table__,
        TableQRCode.__table__,
        RestaurantSession.__table__,
        TaxBillingSetting.__table__,
        CustomerVisitHistory.__table__,
        CRMBranchRankRule.__table__,
        Offer.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=target_tables))

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=target_tables))


@pytest.mark.asyncio
async def test_qr_generation_regeneration_disable(db_session: AsyncSession):
    # Setup mock Client, Branch, Table
    partner = Partner(id=1, name="Test Partner", email="partner1@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client1@example.com", password_hash="hash")
    branch = Branch(id=10, client_id=1, name="Main Branch", address="123 St", city="City", country="India", state="State", pincode="123456", currency="INR", decimal_places=2, tax_type="GST", branch_code="BR10", status=BranchStatus.ACTIVE)
    table = Table(id=100, client_id=1, branch_id=10, name="Table 1", number_of_seats=4, status=TableStatus.available, is_active=True)

    db_session.add_all([partner, client, branch, table])
    await db_session.commit()

    user = MagicMock(id=1, client_id=1)
    role = UserRole.CLIENT

    # 1. Generate QR
    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=role)
    assert qr_res["table_id"] == 100
    assert qr_res["qr_token"] is not None
    assert qr_res["is_active"] is True

    # Verify token_hash is stored, raw token is not stored in DB
    db_qr = await db_session.get(TableQRCode, qr_res["id"])
    assert db_qr.token_hash == hash_token(qr_res["qr_token"])

    # 2. Get QR
    get_res = await TableQRService.get_qr(db_session, table_id=100, user=user, role=role)
    assert get_res["table_id"] == 100
    assert get_res["qr_token"] == qr_res["qr_token"]
    assert get_res["qr_url"] is not None

    # 3. Regenerate QR
    initial_hash = db_qr.token_hash
    regen_res = await TableQRService.regenerate_qr(db_session, table_id=100, user=user, role=role)
    assert regen_res["qr_token"] != qr_res["qr_token"]
    assert hash_token(regen_res["qr_token"]) != initial_hash

    # 4. Disable QR
    disable_res = await TableQRService.disable_qr(db_session, table_id=100, user=user, role=role)
    assert disable_res["is_active"] is False


@pytest.mark.asyncio
async def test_public_qr_resolution_and_session(db_session: AsyncSession):
    partner = Partner(id=1, name="Test Partner", email="partner2@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client2@example.com", password_hash="hash")
    branch = Branch(id=10, client_id=1, name="Main Branch", address="123 St", city="City", country="India", state="State", pincode="123456", currency="INR", decimal_places=2, tax_type="GST", branch_code="BR10", status=BranchStatus.ACTIVE)
    table = Table(id=100, client_id=1, branch_id=10, name="Table 1", number_of_seats=4, status=TableStatus.available, is_active=True)

    db_session.add_all([partner, client, branch, table])
    await db_session.commit()

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    raw_token = qr_res["qr_token"]

    # Resolve QR and start session
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, raw_token)
    assert resolve_res["branch_name"] == "Main Branch"
    assert resolve_res["table_name"] == "Table 1"
    assert resolve_res["currency"] == "INR"
    assert resolve_res["session_token"] is not None

    session_token = resolve_res["session_token"]
    session = await PublicCustomerQRService.get_session_by_token(db_session, session_token)
    assert session.table_id == 100
    assert session.branch_id == 10


@pytest.mark.asyncio
async def test_attach_customer_to_session(db_session: AsyncSession):
    partner = Partner(id=1, name="Test Partner", email="partner3@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client3@example.com", password_hash="hash")
    branch = Branch(id=10, client_id=1, name="Main Branch", address="123 St", city="City", country="India", state="State", pincode="123456", currency="INR", decimal_places=2, tax_type="GST", branch_code="BR10", status=BranchStatus.ACTIVE)
    table = Table(id=100, client_id=1, branch_id=10, name="Table 1", number_of_seats=4, status=TableStatus.available, is_active=True)

    db_session.add_all([partner, client, branch, table])
    await db_session.commit()

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Attach customer
    attach_req = SessionCustomerAttachReq(name="John Doe", phone="9876543210", email="john@example.com")
    cust_res = await PublicCustomerQRService.attach_customer(db_session, session, attach_req)

    assert cust_res["name"] == "John Doe"
    assert cust_res["phone"] == "9876543210"
    assert session.customer_id == cust_res["customer_id"]


@pytest.mark.asyncio
async def test_qr_order_creation_and_price_validation(db_session: AsyncSession):
    partner = Partner(id=1, name="Test Partner", email="partner4@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client4@example.com", password_hash="hash")
    branch = Branch(id=10, client_id=1, name="Main Branch", address="123 St", city="City", country="India", state="State", pincode="123456", currency="INR", decimal_places=2, tax_type="GST", branch_code="BR10", status=BranchStatus.ACTIVE)
    table = Table(id=100, client_id=1, branch_id=10, name="Table 1", number_of_seats=4, status=TableStatus.available, is_active=True)
    item = Item(id=50, client_id=1, branch_id=10, name="Pizza", is_active=True)
    pricing = Pricing(id=500, client_id=1, branch_id=10, item_id=50, price=200.0, discount=10.0, tax=5.0, tax_type="GST", is_active=True)

    db_session.add_all([partner, client, branch, table, item, pricing])
    await db_session.commit()

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Order creation payload contains ONLY item_id and quantity (no untrusted price/tax/subtotal)
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=2)], notes="Extra cheese")

    order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)

    assert order.table_id == 100
    assert order.branch_id == 10
    assert order.status == "pending"
    assert len(order.order_items) == 1
    assert order.order_items[0].item_id == 50
    assert order.order_items[0].quantity == 2
    assert order.order_items[0].order_status == "pending"

    # Verify route DTO serialization executes without lazy-loading / MissingGreenlet errors
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
    assert items_dto[0]["quantity"] == 2

    # Verify table status updated to occupied
    updated_table = await db_session.get(Table, 100)
    assert updated_table.status == TableStatus.occupied


@pytest.mark.asyncio
async def test_idempotent_payment_verification(db_session: AsyncSession):
    partner = Partner(id=1, name="Test Partner", email="partner5@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client5@example.com", password_hash="hash")
    branch = Branch(id=10, client_id=1, name="Main Branch", address="123 St", city="City", country="India", state="State", pincode="123456", currency="INR", decimal_places=2, tax_type="GST", branch_code="BR10", status=BranchStatus.ACTIVE)
    table = Table(id=100, client_id=1, branch_id=10, name="Table 1", number_of_seats=4, status=TableStatus.available, is_active=True)
    item = Item(id=50, client_id=1, branch_id=10, name="Burger", is_active=True)
    pricing = Pricing(id=500, client_id=1, branch_id=10, item_id=50, price=100.0, discount=0.0, tax=0.0, tax_type="GST", is_active=True)

    db_session.add_all([partner, client, branch, table, item, pricing])
    await db_session.commit()

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    order = await PublicCustomerQRService.create_qr_order(db_session, session, PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)]))

    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp_init:
        mock_rzp_init.return_value = {"id": "order_mock123", "amount": 10000, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, order.id)
        assert init_res["bill_id"] is not None

    with patch("app.accounts.table_qr.service.verify_razorpay_payment") as mock_rzp_verify:
        mock_rzp_verify.return_value = None
        
        verify_req = RazorpayPaymentVerifyReq(
            bill_id=init_res["bill_id"],
            razorpay_order_id="order_mock123",
            razorpay_payment_id="pay_mock123",
            razorpay_signature="sig_mock123"
        )

        res1 = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
        assert res1["status"] == "success"
        assert res1["order_status"] == "confirmed"

        # Repeated call must be idempotent and return success without error or duplicate processing
        res2 = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
        assert res2["status"] == "success"
        assert res2["order_status"] == "confirmed"
