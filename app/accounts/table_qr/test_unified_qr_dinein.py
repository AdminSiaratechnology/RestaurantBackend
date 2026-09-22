import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.ext.compiler import compiles

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
from app.accounts.table_qr.service import TableQRService, PublicCustomerQRService
from app.accounts.table_qr.schema import (
    SessionCustomerAttachReq,
    PublicOrderCreateReq,
    PublicOrderItemReq,
    RazorpayPaymentVerifyReq,
)
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.bill.service import complete_bill_transaction, get_or_create_bill_for_order
from app.accounts.payment.model import Payment
from app.accounts.order.enum import OrderType
from app.accounts.order.model import Order, OrderItem
from app.accounts.tax.model import TaxBillingSetting
from app.accounts.crm.customer_history.model import CustomerVisitHistory
from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.crm.loyalty.model import CustomerLoyaltyAccount, LoyaltyTransaction
from app.accounts.offer.model import Offer

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
        CustomerLoyaltyAccount.__table__,
        LoyaltyTransaction.__table__,
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


async def _setup_branch_with_taxes_and_menu(db: AsyncSession):
    partner = Partner(id=1, name="Test Partner", email="partner@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client@example.com", password_hash="hash")
    branch = Branch(
        id=10,
        client_id=1,
        name="Main Branch",
        address="123 St",
        city="City",
        country="India",
        state="State",
        pincode="123456",
        currency="INR",
        decimal_places=2,
        tax_type="GST",
        branch_code="BR10",
        status=BranchStatus.ACTIVE,
    )
    tax_setting = TaxBillingSetting(
        id=1,
        client_id=1,
        branch_id=10,
        default_tax_rate=5.0,
        cgst=2.5,
        sgst=2.5,
        service_charge=10.0,
        enable_service_charge=True,
        enable_tax=True,
        round_off_bill=True,
    )
    table = Table(
        id=100,
        client_id=1,
        branch_id=10,
        name="Table 5",
        number_of_seats=4,
        status=TableStatus.available,
        is_active=True,
    )
    item1 = Item(id=50, client_id=1, branch_id=10, name="Pasta", is_active=True)
    pricing1 = Pricing(
        id=500,
        client_id=1,
        branch_id=10,
        item_id=50,
        price=200.0,
        discount=0.0,
        tax=0.0,
        tax_type="GST",
        is_active=True,
    )
    item2 = Item(id=51, client_id=1, branch_id=10, name="Garlic Bread", is_active=True)
    pricing2 = Pricing(
        id=501,
        client_id=1,
        branch_id=10,
        item_id=51,
        price=100.0,
        discount=0.0,
        tax=0.0,
        tax_type="GST",
        is_active=True,
    )

    db.add_all([partner, client, branch, tax_setting, table, item1, pricing1, item2, pricing2])
    await db.commit()
    return branch, table, item1, item2


@pytest.mark.asyncio
async def test_qr_and_dinein_share_same_bill_tax_calculation(db_session: AsyncSession):
    """
    Scenario 1: Verify QR order bill creation uses the exact same tax settings,
    service charge, CGST/SGST, and rounding as DINE-IN orders.
    """
    branch, table, item1, item2 = await _setup_branch_with_taxes_and_menu(db_session)

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=table.id, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Create QR Order: 2x Pasta (400) + 1x Garlic Bread (100) = 500 Subtotal
    order_req = PublicOrderCreateReq(
        items=[
            PublicOrderItemReq(item_id=50, quantity=2),
            PublicOrderItemReq(item_id=51, quantity=1),
        ]
    )
    qr_order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
    assert qr_order.total_amount == 500.0

    # Initiate payment creates bill via get_or_create_bill_for_order
    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp:
        mock_rzp.return_value = {"id": "order_mock1", "amount": 57500, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, qr_order.id)

    qr_bill = await db_session.get(Bill, init_res["bill_id"])
    assert qr_bill is not None
    assert qr_bill.subtotal == 500.0
    # 5% tax on 500 = 25.0 (12.50 CGST + 12.50 SGST)
    assert qr_bill.cgst_amount == 12.5
    assert qr_bill.sgst_amount == 12.5
    assert qr_bill.tax_total == 25.0
    # 10% service charge on 500 = 50.0
    assert qr_bill.service_charge_percent == 10.0
    assert qr_bill.service_charge_amount == 50.0
    # Total = 500 + 25 + 50 = 575.0
    assert qr_bill.grand_total == 575.0
    assert qr_bill.final_amount == 575.0


@pytest.mark.asyncio
async def test_qr_payment_triggers_unified_crm_visit_history(db_session: AsyncSession):
    """
    Scenario 2: Verify QR payment completion creates CustomerVisitHistory,
    updates total_spend, current_spend, and visit stats identical to POS DINE-IN.
    """
    branch, table, item1, _ = await _setup_branch_with_taxes_and_menu(db_session)

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=table.id, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Attach a real customer with phone
    attach_req = SessionCustomerAttachReq(name="Alice Smith", phone="9988776655", email="alice@example.com")
    cust_res = await PublicCustomerQRService.attach_customer(db_session, session, attach_req)
    customer_id = cust_res["customer_id"]
    assert customer_id is not None

    # Create Order (1x Pasta = 200)
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    qr_order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)

    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp:
        mock_rzp.return_value = {"id": "order_mock2", "amount": 23000, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, qr_order.id)

    with patch("app.accounts.table_qr.service.verify_razorpay_payment"):
        verify_req = RazorpayPaymentVerifyReq(
            bill_id=init_res["bill_id"],
            razorpay_order_id="order_mock2",
            razorpay_payment_id="pay_mock2",
            razorpay_signature="sig_mock2",
        )
        res = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
        assert res["status"] == "success"

    # Verify Customer stats in DB
    customer = await db_session.get(Customer, customer_id)
    assert customer is not None
    # 200 subtotal + 10 tax + 20 svc = 230.0
    assert customer.total_spend == 230.0
    assert customer.current_spend == 230.0

    # Verify CustomerVisitHistory recorded
    vh_res = await db_session.execute(
        select(CustomerVisitHistory).where(CustomerVisitHistory.customer_id == customer_id)
    )
    visit = vh_res.scalar_one_or_none()
    assert visit is not None
    assert visit.bill_id == init_res["bill_id"]
    assert visit.order_id == qr_order.id
    assert visit.total_amount == 230.0
    assert visit.payment_method == "razorpay"


@pytest.mark.asyncio
async def test_qr_payment_releases_table_and_completes_session(db_session: AsyncSession):
    """
    Scenario 3: Verify table status changes to available and RestaurantSession
    is marked COMPLETED upon payment.
    """
    branch, table, item1, _ = await _setup_branch_with_taxes_and_menu(db_session)

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=table.id, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Create Order -> Table becomes occupied
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    qr_order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
    t = await db_session.get(Table, table.id)
    assert t.status == TableStatus.occupied

    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp:
        mock_rzp.return_value = {"id": "order_mock3", "amount": 23000, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, qr_order.id)

    with patch("app.accounts.table_qr.service.verify_razorpay_payment"):
        verify_req = RazorpayPaymentVerifyReq(
            bill_id=init_res["bill_id"],
            razorpay_order_id="order_mock3",
            razorpay_payment_id="pay_mock3",
            razorpay_signature="sig_mock3",
        )
        await PublicCustomerQRService.verify_payment(db_session, session, verify_req)

    # Table is released to available
    t_after = await db_session.get(Table, table.id)
    assert t_after.status == TableStatus.available

    # RestaurantSession marked completed
    sess_after = await db_session.get(RestaurantSession, session.id)
    assert sess_after.status == SessionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_qr_name_only_diner_no_dummy_guest_created(db_session: AsyncSession):
    """
    Scenario 4: When customer attaches with name only (no phone/email),
    verify NO dummy 'GUEST-QR-...' customer record is inserted.
    """
    branch, table, item1, _ = await _setup_branch_with_taxes_and_menu(db_session)

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=table.id, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Attach with name only
    attach_req = SessionCustomerAttachReq(name="Walk-in QR Diner", phone=None, email=None)
    cust_res = await PublicCustomerQRService.attach_customer(db_session, session, attach_req)
    assert cust_res["customer_id"] is None
    assert cust_res["name"] == "Walk-in QR Diner"

    # Verify no dummy customer was created
    all_custs = (await db_session.execute(select(Customer))).scalars().all()
    assert len(all_custs) == 0

    # Order and payment should succeed seamlessly
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    qr_order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
    assert qr_order.customer_name == "QR Guest"

    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp:
        mock_rzp.return_value = {"id": "order_mock4", "amount": 23000, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, qr_order.id)

    with patch("app.accounts.table_qr.service.verify_razorpay_payment"):
        verify_req = RazorpayPaymentVerifyReq(
            bill_id=init_res["bill_id"],
            razorpay_order_id="order_mock4",
            razorpay_payment_id="pay_mock4",
            razorpay_signature="sig_mock4",
        )
        res = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
        assert res["status"] == "success"

    # Bill completed and table released
    bill = await db_session.get(Bill, init_res["bill_id"])
    assert bill.payment_status == PaymentStatus.complete
    tbl = await db_session.get(Table, table.id)
    assert tbl.status == TableStatus.available


@pytest.mark.asyncio
async def test_qr_payment_idempotency_guard(db_session: AsyncSession):
    """
    Scenario 5: Calling verify_payment multiple times does not duplicate
    spend or create duplicate visit records.
    """
    branch, table, item1, _ = await _setup_branch_with_taxes_and_menu(db_session)

    user = MagicMock(id=1, client_id=1)
    qr_res = await TableQRService.generate_qr(db_session, table_id=table.id, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    attach_req = SessionCustomerAttachReq(name="Bob", phone="9123456780", email=None)
    cust_res = await PublicCustomerQRService.attach_customer(db_session, session, attach_req)
    customer_id = cust_res["customer_id"]

    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    qr_order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)

    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp:
        mock_rzp.return_value = {"id": "order_mock5", "amount": 23000, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, qr_order.id)

    verify_req = RazorpayPaymentVerifyReq(
        bill_id=init_res["bill_id"],
        razorpay_order_id="order_mock5",
        razorpay_payment_id="pay_mock5",
        razorpay_signature="sig_mock5",
    )

    with patch("app.accounts.table_qr.service.verify_razorpay_payment"):
        # First verification
        res1 = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
        assert res1["status"] == "success"

        # Second verification (idempotent replay)
        res2 = await PublicCustomerQRService.verify_payment(db_session, session, verify_req)
        assert res2["status"] == "success"
        assert res2["message"] == "Payment already verified and completed"

    # Only 1 visit history should exist
    visits = (
        await db_session.execute(
            select(CustomerVisitHistory).where(CustomerVisitHistory.customer_id == customer_id)
        )
    ).scalars().all()
    assert len(visits) == 1

    # Customer spend is counted exactly once
    cust = await db_session.get(Customer, customer_id)
    assert cust.total_spend == 230.0


@pytest.mark.asyncio
async def test_pos_bill_payment_uses_unified_completion(db_session: AsyncSession):
    """
    Scenario 6: Verify direct DINE-IN bill completion via complete_bill_transaction
    executes the exact same pipeline (table release, CRM, cache, stats).
    """
    branch, table, item1, _ = await _setup_branch_with_taxes_and_menu(db_session)

    # Customer creates DINE-IN order at table
    customer = Customer(
        client_id=1,
        branch_id=10,
        branch_name="Main Branch",
        name="Charlie",
        phone="9876500000",
        email="charlie@example.com",
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    # Table is occupied
    table.status = TableStatus.occupied
    await db_session.commit()

    order = Order(
        client_id=1,
        branch_id=10,
        table_id=table.id,
        customer_id=customer.id,
        customer_name=customer.name,
        customer_phone=customer.phone,
        order_type=OrderType.DINE_IN,
        total_amount=200.0,
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)

    order_item = OrderItem(
        order_id=order.id,
        item_id=50,
        quantity=1,
        unit_price=200.0,
        subtotal=200.0,
        total_price=200.0,
    )
    db_session.add(order_item)
    await db_session.commit()

    # Generate bill using get_or_create_bill_for_order
    bill = await get_or_create_bill_for_order(db_session, order.id)
    await db_session.commit()
    assert bill.final_amount == 230.0

    # Execute authoritative completion
    completed_bill = await complete_bill_transaction(
        db_session,
        bill=bill,
        payment_method="cash",
        paid_amount=230.0,
        customer_id=customer.id,
    )
    await db_session.commit()

    assert completed_bill.payment_status == PaymentStatus.complete
    assert completed_bill.paid_amount == 230.0
    assert completed_bill.due_amount == 0.0

    # Table released
    tbl = await db_session.get(Table, table.id)
    assert tbl.status == TableStatus.available

    # Visit history recorded
    vh = (
        await db_session.execute(
            select(CustomerVisitHistory).where(CustomerVisitHistory.customer_id == customer.id)
        )
    ).scalar_one_or_none()
    assert vh is not None
    assert vh.total_amount == 230.0
    assert vh.payment_method == "cash"
