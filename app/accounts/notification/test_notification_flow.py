# app/accounts/notification/test_notification_flow.py

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update

from app.db.base import Base
from app.accounts.enum import UserRole
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.branch.model import Branch, statusEnum as BranchStatus
from app.accounts.table.model import Table, TableStatus
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.accounts.customer.model import Customer
from app.accounts.order.model import Order, OrderItem, OrderSource
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.payment.model import Payment
from app.accounts.table_qr.model import TableQRCode, RestaurantSession, SessionStatus
from app.accounts.table_qr.service import TableQRService, PublicCustomerQRService
from app.accounts.table_qr.schema import (
    PublicOrderCreateReq,
    PublicOrderItemReq,
    SessionCustomerAttachReq,
)
from app.accounts.offer.model import Offer, OfferType
from app.accounts.notification.model import (
    DeviceToken,
    CustomerNotificationPreference,
    Notification,
    NotificationType,
)
from app.accounts.notification.service import NotificationService
from app.accounts.staff.model import Staff, StaffRole

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
        Staff.__table__,
        Item.__table__,
        Pricing.__table__,
        Customer.__table__,
        Order.__table__,
        OrderItem.__table__,
        Bill.__table__,
        Payment.__table__,
        Offer.__table__,
        TableQRCode.__table__,
        RestaurantSession.__table__,
        DeviceToken.__table__,
        CustomerNotificationPreference.__table__,
        Notification.__table__,
    ]

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=target_tables))

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=target_tables))


async def setup_base_fixtures(db: AsyncSession):
    partner = Partner(id=1, name="Test Partner", email="partner@example.com", password_hash="hash")
    client = Client(id=1, partner_id=1, name="Test Client", email="client@example.com", password_hash="hash")
    branch = Branch(
        id=10,
        client_id=1,
        name="Downtown Branch",
        address="123 Main St",
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
    table = Table(id=100, client_id=1, branch_id=10, name="Table 12", number_of_seats=4, status=TableStatus.available, is_active=True)
    chef = Staff(id=1, name="Chef Mario", email="chef@example.com", password_hash="hash", role=StaffRole.chef, client_id=1, branch_id=10)
    item = Item(id=50, client_id=1, branch_id=10, name="Margherita Pizza", is_active=True)
    pricing = Pricing(id=500, client_id=1, branch_id=10, item_id=50, price=250.0, discount=0.0, tax=5.0, tax_type="GST", is_active=True)

    db.add_all([partner, client, branch, table, chef, item, pricing])
    await db.commit()

    # Chef device token
    chef_token = DeviceToken(
        token="chef_fcm_token_12345",
        platform="web",
        client_id=1,
        branch_id=10,
        user_id=1,
        is_active=True,
        notifications_enabled=True,
    )
    db.add(chef_token)
    await db.commit()

    return {
        "client": client,
        "branch": branch,
        "table": table,
        "chef": chef,
        "item": item,
        "pricing": pricing,
    }


@pytest.mark.asyncio
async def test_qr_token_registration_and_refresh(db_session: AsyncSession):
    fixtures = await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    # 1. Generate QR & Resolve Session
    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session_token = resolve_res["session_token"]
    session = await PublicCustomerQRService.get_session_by_token(db_session, session_token)

    # 2. Register anonymous QR device token
    dt1 = await NotificationService.register_or_update_device_token(
        db=db_session,
        token="device_token_mobile_aaa",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
        device_id="client_device_1",
    )

    assert dt1.token == "device_token_mobile_aaa"
    assert dt1.qr_session_id == session.id
    assert dt1.customer_id is None
    assert dt1.is_active is True

    # 3. Token refresh on same device (e.g. browser refreshes token)
    dt2 = await NotificationService.register_or_update_device_token(
        db=db_session,
        token="device_token_mobile_bbb",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
        device_id="client_device_1",
    )

    # Verify old token deactivated and new token active
    old_dt = await db_session.get(DeviceToken, dt1.id)
    assert old_dt.is_active is False
    assert dt2.is_active is True
    assert dt2.token == "device_token_mobile_bbb"


@pytest.mark.asyncio
async def test_customer_attachment_and_multiple_devices(db_session: AsyncSession):
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Anonymous token
    await NotificationService.register_or_update_device_token(
        db=db_session,
        token="device_phone_token",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
        device_id="phone_1",
    )

    # Attach customer details
    attach_req = SessionCustomerAttachReq(name="Jane Doe", phone="9988776655", email="jane@example.com")
    cust_res = await PublicCustomerQRService.attach_customer(db_session, session, attach_req)
    cust_id = cust_res["customer_id"]

    # Verify token linked to customer
    token_query = await db_session.execute(select(DeviceToken).where(DeviceToken.token == "device_phone_token"))
    dt_phone = token_query.scalar_one()
    assert dt_phone.customer_id == cust_id

    # Customer also opens from their tablet
    dt_tablet = await NotificationService.register_or_update_device_token(
        db=db_session,
        token="device_tablet_token",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        customer_id=cust_id,
        device_id="tablet_1",
    )

    # Multiple active devices for same customer
    cust_tokens_res = await db_session.execute(
        select(DeviceToken).where(DeviceToken.customer_id == cust_id, DeviceToken.is_active == True)
    )
    active_tokens = list(cust_tokens_res.scalars().all())
    assert len(active_tokens) == 2


@pytest.mark.asyncio
async def test_order_creation_triggers_kitchen_and_session_notifications(db_session: AsyncSession):
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    await NotificationService.register_or_update_device_token(
        db=db_session,
        token="customer_active_order_token",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
    )

    # Create QR order
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=2)], notes="Crispy crust")
    order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)

    # Verify order created
    assert order.id is not None
    assert order.status == "pending"

    # Verify notification records generated for kitchen and session
    notifs_res = await db_session.execute(
        select(Notification).where(Notification.order_id == order.id, Notification.type == NotificationType.NEW_ORDER.value)
    )
    notifs = list(notifs_res.scalars().all())
    assert len(notifs) >= 1
    assert any("New Order #" in n.title for n in notifs)


@pytest.mark.asyncio
async def test_order_status_transitions_and_duplicate_prevention(db_session: AsyncSession):
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    await NotificationService.register_or_update_device_token(
        db=db_session,
        token="cust_live_order_token",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
    )

    order = await PublicCustomerQRService.create_qr_order(
        db_session, session, PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    )

    # Transition: pending -> preparing
    res_prep = await NotificationService.send_order_status_update(db_session, order, "pending", "preparing")
    assert res_prep["sent_count"] >= 1

    # Verify duplicate prevention: preparing -> preparing does not send another
    res_dup = await NotificationService.send_order_status_update(db_session, order, "preparing", "preparing")
    assert res_dup["sent_count"] == 0

    # Verify DB-level duplicate prevention: even if caller passes old_status='pending', DB check prevents duplicate
    res_dup2 = await NotificationService.send_order_status_update(db_session, order, "pending", "preparing")
    assert res_dup2["sent_count"] == 0

    # Transition: preparing -> ready
    res_ready = await NotificationService.send_order_status_update(db_session, order, "preparing", "ready")
    assert res_ready["sent_count"] >= 1

    # Transition: ready -> served
    res_served = await NotificationService.send_order_status_update(db_session, order, "ready", "served")
    assert res_served["sent_count"] >= 1

    # Check notification history
    notifs_res = await db_session.execute(
        select(Notification).where(Notification.order_id == order.id)
    )
    notifs = list(notifs_res.scalars().all())
    types = [n.type for n in notifs]
    assert NotificationType.ORDER_PREPARING.value in types
    assert NotificationType.ORDER_READY.value in types
    assert NotificationType.ORDER_SERVED.value in types

    # Verify exactly 1 notification per status type exists for this order (no duplicates)
    assert len([n for n in notifs if n.type == NotificationType.ORDER_PREPARING.value]) == 1
    assert len([n for n in notifs if n.type == NotificationType.ORDER_READY.value]) == 1
    assert len([n for n in notifs if n.type == NotificationType.ORDER_SERVED.value]) == 1


@pytest.mark.asyncio
async def test_bill_completion_preserves_device_token(db_session: AsyncSession):
    """
    CRITICAL STEP 11 TEST:
    Verify that when order is paid and bill is completed,
    the customer's FCM device token is STILL ACTIVE and NOT DELETED.
    """
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    dt = await NotificationService.register_or_update_device_token(
        db=db_session,
        token="persistent_customer_token_999",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
    )

    order = await PublicCustomerQRService.create_qr_order(
        db_session, session, PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    )

    with patch("app.accounts.table_qr.service.create_razorpay_order") as mock_rzp_init:
        mock_rzp_init.return_value = {"id": "order_mock123", "amount": 25000, "currency": "INR"}
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session, order.id)
        bill_id = init_res["bill_id"]

    from app.accounts.table_qr.schema import RazorpayPaymentVerifyReq
    with patch("app.accounts.table_qr.service.verify_razorpay_payment") as mock_rzp_verify:
        mock_rzp_verify.return_value = None
        verify_req = RazorpayPaymentVerifyReq(
            bill_id=bill_id,
            razorpay_order_id="order_mock123",
            razorpay_payment_id="pay_mock123",
            razorpay_signature="sig_mock123",
        )
        await PublicCustomerQRService.verify_payment(db_session, session, verify_req)

    # 1. Verify bill is completed
    bill = await db_session.get(Bill, bill_id)
    assert bill.payment_status == PaymentStatus.complete

    # 2. Verify FCM token is STILL active! (BILL COMPLETED != DELETE FCM TOKEN)
    token_check = await db_session.get(DeviceToken, dt.id)
    assert token_check is not None
    assert token_check.is_active is True
    assert token_check.notifications_enabled is True

    # 3. Post-Bill Engagement: Restaurant sends offer notification to customer
    offer = Offer(
        id=25,
        branch_id=10,
        offer_name="Weekend Special 20% OFF",
        description="Get 20% off your next order.",
        offer_type=OfferType.PERCENTAGE_OFF,
        discount_value=20.0,
        valid_from=datetime.now(timezone.utc),
        valid_to=datetime.now(timezone.utc),
        is_active=True,
    )
    db_session.add(offer)
    await db_session.commit()

    offer_send_res = await NotificationService.send_offer_campaign(
        db=db_session,
        offer_id=25,
        target_type="branch",
        target_id=10,
    )
    assert offer_send_res["sent_count"] >= 1

    # Verify notification history saved for offer
    offer_notif_res = await db_session.execute(
        select(Notification).where(Notification.offer_id == 25)
    )
    offer_notif = offer_notif_res.scalar_one_or_none()
    assert offer_notif is not None
    assert offer_notif.type == NotificationType.OFFER.value
    assert "Weekend Special" in offer_notif.title


@pytest.mark.asyncio
async def test_resilience_firebase_failure_does_not_break_rms(db_session: AsyncSession):
    """
    MANDATORY REQUIREMENT:
    Firebase failure MUST NOT roll back or break RMS orders, payments, or bills.
    """
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    await NotificationService.register_or_update_device_token(
        db=db_session,
        token="token_fail_test",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
    )

    # Mock send_to_tokens to raise an unexpected runtime error inside Firebase call
    with patch("app.accounts.notification.service._init_firebase") as mock_fb:
        mock_messaging = MagicMock()
        mock_messaging.send_each_for_multicast.side_effect = Exception("Firebase connection timeout 504")
        mock_fb.return_value = mock_messaging

        # Order creation must succeed even if FCM throws exception
        order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
        order = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
        assert order.id is not None
        assert order.status == "pending"

        # Table is still occupied
        table = await db_session.get(Table, 100)
        assert table.status == TableStatus.occupied


@pytest.mark.asyncio
async def test_call_for_bill_flow_and_rms_bell(db_session: AsyncSession):
    """
    FLOW 2 TEST:
    QR customer clicks Call for Bill:
    1. NotificationService.send_bill_requested generates BILL_REQUESTED notification in DB
    2. Scoped to client_id, branch_id, table_id, qr_session_id
    3. Target link points to /Bills
    4. Notification sent to staff tokens, never customer tokens
    """
    fixtures = await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # Register customer token
    await NotificationService.register_or_update_device_token(
        db=db_session,
        token="cust_bill_req_token",
        platform="web",
        client_id=session.client_id,
        branch_id=session.branch_id,
        qr_session_id=session.id,
    )

    # Trigger Call for Bill
    bill_notif_res = await NotificationService.send_bill_requested(db_session, session)
    assert bill_notif_res["success"] is True
    notif_id = bill_notif_res["notification_id"]
    assert notif_id is not None

    # Verify notification created in DB
    notif = await db_session.get(Notification, notif_id)
    assert notif is not None
    assert notif.type == NotificationType.BILL_REQUESTED.value
    assert notif.client_id == 1
    assert notif.branch_id == 10
    assert notif.data.get("table_id") == "100"
    assert notif.qr_session_id == session.id
    assert notif.data.get("target_link") == "/Bills"
    assert "Table 12" in notif.body

    # Verify unread count for branch staff
    unread = await NotificationService.get_unread_count(
        db=db_session,
        client_id=1,
        branch_id=10,
    )
    assert unread >= 1


@pytest.mark.asyncio
async def test_public_notifications_session_isolation(db_session: AsyncSession):
    """
    QR SESSION ISOLATION TEST:
    Session A must NEVER see Session B's alerts,
    and public sessions must NEVER see internal staff alerts (BILL_REQUESTED, NEW_ORDER).
    """
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    # Table 100 Session A
    qr_res_a = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res_a = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res_a["qr_token"])
    session_a = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res_a["session_token"])

    # Table 101 Session B
    table_b = Table(id=101, client_id=1, branch_id=10, name="Table 14", number_of_seats=2, status=TableStatus.available, is_active=True)
    db_session.add(table_b)
    await db_session.commit()

    qr_res_b = await TableQRService.generate_qr(db_session, table_id=101, user=user, role=UserRole.CLIENT)
    resolve_res_b = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res_b["qr_token"])
    session_b = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res_b["session_token"])

    # Create order for Session A
    order_a = await PublicCustomerQRService.create_qr_order(
        db_session, session_a, PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    )
    await NotificationService.send_order_status_update(db_session, order_a, "pending", "preparing")

    # Call for bill from Session A
    await NotificationService.send_bill_requested(db_session, session_a)

    # Create order for Session B
    order_b = await PublicCustomerQRService.create_qr_order(
        db_session, session_b, PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=2)])
    )
    await NotificationService.send_order_status_update(db_session, order_b, "pending", "ready")

    # Fetch public alerts for Session A:
    # Query mirroring public_router GET /public/notifications
    query_a = select(Notification).where(
        Notification.qr_session_id == session_a.id,
        Notification.type.notin_([NotificationType.BILL_REQUESTED.value, NotificationType.NEW_ORDER.value]),
    )
    res_a = await db_session.execute(query_a)
    notifs_a = list(res_a.scalars().all())

    # Verify Session A gets its preparing update
    assert any(n.type == NotificationType.ORDER_PREPARING.value for n in notifs_a)
    # Verify Session A NEVER gets Session B's ready update
    assert not any(n.type == NotificationType.ORDER_READY.value for n in notifs_a)
    # Verify Session A NEVER gets internal staff alerts like BILL_REQUESTED or NEW_ORDER
    assert not any(n.type == NotificationType.BILL_REQUESTED.value for n in notifs_a)
    assert not any(n.type == NotificationType.NEW_ORDER.value for n in notifs_a)


@pytest.mark.asyncio
async def test_order_ready_alerts_waitstaff(db_session: AsyncSession):
    """
    WAITSTAFF ALERT TEST:
    When order status transitions to 'ready', branch waitstaff must receive notification.
    """
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    # Add Waiter staff & token
    waiter = Staff(id=2, name="Waiter Alex", email="waiter@example.com", password_hash="hash", role=StaffRole.waiter, client_id=1, branch_id=10)
    db_session.add(waiter)
    await db_session.commit()

    waiter_token = DeviceToken(
        token="waiter_alex_fcm_token",
        platform="web",
        client_id=1,
        branch_id=10,
        user_id=2,
        is_active=True,
        notifications_enabled=True,
    )
    db_session.add(waiter_token)
    await db_session.commit()

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    order = await PublicCustomerQRService.create_qr_order(
        db_session, session, PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=1)])
    )

    # Transition to ready
    res_ready = await NotificationService.send_order_status_update(db_session, order, "preparing", "ready")
    assert res_ready["success"] is True
    # At least 1 delivery was dispatched to waiter/tokens
    assert res_ready["sent_count"] >= 1


@pytest.mark.asyncio
async def test_main_rms_tenant_isolation_and_mark_read(db_session: AsyncSession):
    """
    TENANT ISOLATION & READ STATUS TEST:
    Client 1 / Branch 10 notifications must NOT be visible to Client 2 / Branch 20.
    Marking read and mark all read works accurately.
    """
    await setup_base_fixtures(db_session)

    # Create Client 2 & Branch 20
    client2 = Client(id=2, partner_id=1, name="Client 2", email="client2@example.com", password_hash="hash")
    branch2 = Branch(
        id=20,
        client_id=2,
        name="Uptown Branch",
        address="456 Oak St",
        city="City",
        country="India",
        state="State",
        pincode="123456",
        currency="INR",
        decimal_places=2,
        tax_type="GST",
        branch_code="BR20",
        status=BranchStatus.ACTIVE,
    )
    db_session.add_all([client2, branch2])
    await db_session.commit()

    # Create notification for Client 1 / Branch 10
    notif1 = Notification(
        client_id=1,
        branch_id=10,
        type=NotificationType.BILL_REQUESTED.value,
        title="Bill Requested",
        body="Table 12 bill requested",
        is_read=False,
    )
    # Create notification for Client 2 / Branch 20
    notif2 = Notification(
        client_id=2,
        branch_id=20,
        type=NotificationType.BILL_REQUESTED.value,
        title="Bill Requested",
        body="Table 1 bill requested",
        is_read=False,
    )
    db_session.add_all([notif1, notif2])
    await db_session.commit()

    # Client 1 queries notifications
    c1_notifs = await NotificationService.get_user_notifications(db_session, client_id=1, branch_id=10)
    assert len(c1_notifs) == 1
    assert c1_notifs[0].id == notif1.id

    # Client 2 queries notifications
    c2_notifs = await NotificationService.get_user_notifications(db_session, client_id=2, branch_id=20)
    assert len(c2_notifs) == 1
    assert c2_notifs[0].id == notif2.id

    # Mark notif1 as read
    read_ok = await NotificationService.mark_as_read(db_session, notif1.id, user_id=None, client_id=1)
    assert read_ok is True
    notif1_reloaded = await db_session.get(Notification, notif1.id)
    assert notif1_reloaded.is_read is True

    # Mark all read for Client 2
    marked_count = await NotificationService.mark_all_as_read(db_session, user_id=None, client_id=2, branch_id=20)
    assert marked_count == 1
    notif2_reloaded = await db_session.get(Notification, notif2.id)
    assert notif2_reloaded.is_read is True


@pytest.mark.asyncio
async def test_call_for_bill_validation_and_notification(db_session: AsyncSession):
    """
    TEST CALL FOR BILL VALIDATION & NOTIFICATION:
    1. Rejects if no orders exist for the session (HTTP 400).
    2. Rejects if orders exist but are not yet served, e.g. 'pending' or 'preparing' (HTTP 400).
    3. Rejects if all orders were cancelled (HTTP 400).
    4. Allows if all active orders are served, sets session.bill_requested=True,
       and dispatches BILL_REQUESTED notification.
    """
    from fastapi import HTTPException
    from app.accounts.table_qr.public_router import call_for_bill_endpoint

    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # 1. No orders placed yet -> should fail with 400
    with pytest.raises(HTTPException) as exc_info:
        await call_for_bill_endpoint(db=db_session, session=session)
    assert exc_info.value.status_code == 400
    assert "No orders have been placed" in exc_info.value.detail

    # 2. Place an order -> status defaults to 'pending'
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=2)])
    order1 = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
    assert order1.status == "pending"

    # Order is pending -> should fail with 400 unserved
    with pytest.raises(HTTPException) as exc_info:
        await call_for_bill_endpoint(db=db_session, session=session)
    assert exc_info.value.status_code == 400
    assert "All orders must be served before requesting the bill" in exc_info.value.detail

    # 3. Order is cancelled -> should fail with 400 all cancelled
    order1.status = "cancelled"
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await call_for_bill_endpoint(db=db_session, session=session)
    assert exc_info.value.status_code == 400
    assert "All placed orders have been cancelled" in exc_info.value.detail

    # 4. Place a second order and update status to 'served'
    order2 = await PublicCustomerQRService.create_qr_order(db_session, session, order_req)
    order2.status = "served"
    await db_session.commit()

    # Now call for bill should succeed
    result = await call_for_bill_endpoint(db=db_session, session=session)

    assert result["success"] is True
    assert "Bill requested" in result["message"]
    assert result["order_id"] == order2.id

    # Verify notification created in PostgreSQL
    notif_query = await db_session.execute(
        select(Notification).where(
            Notification.type == NotificationType.BILL_REQUESTED.value,
            Notification.client_id == session.client_id,
        )
    )
    bill_notif = notif_query.scalar_one_or_none()
    assert bill_notif is not None
    assert "Bill requested" in bill_notif.title


@pytest.mark.asyncio
async def test_completed_bill_clears_session_and_customer_details(db_session: AsyncSession):
    """
    TEST: After a customer's bill is paid and completed:
    1. The old session is marked COMPLETED.
    2. Table status is marked available.
    3. Rescanning the table QR code yields a fresh session with customer_info = None
       (previous customer details like Rahul, 7300397982 are cleared).
    4. Auto-closing: Even if session was still marked active, resolve_qr_and_start_session
       detects that all orders have completed bills, marks old session COMPLETED,
       and starts fresh for the new customer.
    """
    await setup_base_fixtures(db_session)
    user = MagicMock(id=1, client_id=1)

    qr_res = await TableQRService.generate_qr(db_session, table_id=100, user=user, role=UserRole.CLIENT)
    resolve_res = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    session1 = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res["session_token"])

    # 1. Attach Customer (Rahul)
    attach_req = SessionCustomerAttachReq(name="Rahul", phone="7300397982")
    await PublicCustomerQRService.attach_customer(db_session, session1, attach_req)

    # 2. Place Order
    order_req = PublicOrderCreateReq(items=[PublicOrderItemReq(item_id=50, quantity=2)])
    order = await PublicCustomerQRService.create_qr_order(db_session, session1, order_req)
    assert order.id is not None

    # 3. Create Bill via initiate_payment and Mark as Paid (complete)
    with patch("app.accounts.table_qr.service.create_razorpay_order", return_value={"id": "mock_rzp", "amount": 20000, "currency": "INR"}):
        init_res = await PublicCustomerQRService.initiate_payment(db_session, session1, order.id)
    bill = await db_session.get(Bill, init_res["bill_id"])
    bill.payment_status = PaymentStatus.complete
    await db_session.commit()

    # 4. Settle / Free table & session
    table = await db_session.get(Table, 100)
    table.status = TableStatus.available
    session1.status = SessionStatus.COMPLETED.value
    await db_session.commit()

    # 5. Next customer scans the same table QR code
    resolve_res_next = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])

    # Verify: Previous customer details are completely cleared
    assert resolve_res_next["customer"] is None
    assert resolve_res_next["session_token"] != resolve_res["session_token"]

    # 6. Test auto-closing of session in resolve_qr_and_start_session if session was left active
    session2 = await PublicCustomerQRService.get_session_by_token(db_session, resolve_res_next["session_token"])
    await PublicCustomerQRService.attach_customer(db_session, session2, SessionCustomerAttachReq(name="Previous Guy", phone="1111111111"))
    order2 = await PublicCustomerQRService.create_qr_order(db_session, session2, order_req)
    with patch("app.accounts.table_qr.service.create_razorpay_order", return_value={"id": "mock_rzp2", "amount": 10000, "currency": "INR"}):
        init_res2 = await PublicCustomerQRService.initiate_payment(db_session, session2, order2.id)
    bill2 = await db_session.get(Bill, init_res2["bill_id"])
    bill2.payment_status = PaymentStatus.complete
    await db_session.commit()

    # Rescan table without manually closing session2: resolve_qr_and_start_session detects bill is complete and auto-closes it!
    resolve_res_after_auto = await PublicCustomerQRService.resolve_qr_and_start_session(db_session, qr_res["qr_token"])
    assert resolve_res_after_auto["customer"] is None
    assert resolve_res_after_auto["session_token"] != resolve_res_next["session_token"]



