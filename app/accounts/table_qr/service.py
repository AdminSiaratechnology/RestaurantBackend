import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounts.bill.enum import PaymentStatus
from app.accounts.bill.model import Bill
from app.accounts.bill.router import _calculate_bill_totals
from app.accounts.branch.model import Branch, statusEnum as BranchStatus
from app.accounts.crm.customer_history.checkout_service import handle_customer_and_visit
from app.accounts.customer.model import Customer, CustomerTypeEnum
from app.accounts.customer.service import find_or_create_customer
from app.accounts.item.model import Item
from app.accounts.order.enum import OrderType
from app.accounts.order.model import Order, OrderItem, OrderSource
from app.accounts.order.router import (
    compute_total_price,
    order_item_line_snapshot,
    resolve_pricing,
)
from app.accounts.payment.enum import PaymentMethod
from app.accounts.payment.model import Payment
from app.accounts.payment.razorpay_service import (
    RAZORPAY_KEY_ID,
    create_razorpay_order,
    verify_razorpay_payment,
)
from app.accounts.payment.schema import PaymentCreate, PaymentItem
from app.accounts.payment.service import make_payment_service
from app.accounts.pricing.model import Pricing
from app.accounts.table.enum import TableStatus
from app.accounts.table.model import Table
from app.accounts.table_qr.model import RestaurantSession, SessionStatus, TableQRCode
from app.accounts.table_qr.schema import (
    PublicOrderCreateReq,
    RazorpayInitiateOut,
    RazorpayPaymentVerifyReq,
    SessionCustomerAttachReq,
)
from app.core.cache import Cache
from app.core.settings import settings
from app.core.tax import resolve_branch_tax_type


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


class TableQRService:

    @staticmethod
    def get_public_qr_url(token: str) -> str:
        base_url = getattr(settings, "PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
        return f"{base_url}/q/{token}"

    @staticmethod
    async def generate_qr(
        db: AsyncSession,
        table_id: int,
        user: Any,
        role: Any,
    ) -> dict[str, Any]:
        result = await db.execute(
            select(Table).where(Table.id == table_id)
        )
        table = result.scalar_one_or_none()

        if not table or not table.is_active:
            raise HTTPException(
                status_code=404,
                detail="Table not found or inactive",
            )

        if role.name == "STAFF" and user.client_id != table.client_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized for this table",
            )

        if role.name == "CLIENT" and user.id != table.client_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized for this table",
            )

        token = generate_opaque_token()
        token_h = hash_token(token)

        qr_result = await db.execute(
            select(TableQRCode).where(TableQRCode.table_id == table_id)
        )
        qr_code = qr_result.scalar_one_or_none()

        if qr_code:
            qr_code.token_hash = token_h
            qr_code.qr_token = token
            qr_code.is_active = True
            qr_code.updated_at = datetime.now(timezone.utc)
        else:
            qr_code = TableQRCode(
                client_id=table.client_id,
                branch_id=table.branch_id,
                table_id=table.id,
                token_hash=token_h,
                qr_token=token,
                is_active=True,
            )
            db.add(qr_code)

        await db.commit()
        await db.refresh(qr_code)

        qr_url = TableQRService.get_public_qr_url(token)

        return {
            "id": qr_code.id,
            "branch_id": qr_code.branch_id,
            "table_id": qr_code.table_id,
            "qr_token": token,
            "qr_url": qr_url,
            "is_active": qr_code.is_active,
            "created_at": qr_code.created_at,
            "updated_at": qr_code.updated_at,
        }

    @staticmethod
    async def get_qr(
        db: AsyncSession,
        table_id: int,
        user: Any,
        role: Any,
    ) -> dict[str, Any]:
        result = await db.execute(
            select(TableQRCode).where(TableQRCode.table_id == table_id)
        )
        qr_code = result.scalar_one_or_none()

        if not qr_code or not qr_code.is_active:
            raise HTTPException(
                status_code=404,
                detail="QR code not generated for this table",
            )

        if role.name == "STAFF" and user.client_id != qr_code.client_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if role.name == "CLIENT" and user.id != qr_code.client_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # If qr_token is missing on legacy row, populate it safely
        if not qr_code.qr_token:
            token = generate_opaque_token()
            qr_code.qr_token = token
            qr_code.token_hash = hash_token(token)
            await db.commit()
            await db.refresh(qr_code)

        qr_url = TableQRService.get_public_qr_url(qr_code.qr_token)

        return {
            "id": qr_code.id,
            "branch_id": qr_code.branch_id,
            "table_id": qr_code.table_id,
            "qr_token": qr_code.qr_token,
            "qr_url": qr_url,
            "is_active": qr_code.is_active,
            "created_at": qr_code.created_at,
            "updated_at": qr_code.updated_at,
        }

    @staticmethod
    async def regenerate_qr(
        db: AsyncSession,
        table_id: int,
        user: Any,
        role: Any,
    ) -> dict[str, Any]:
        return await TableQRService.generate_qr(db, table_id, user, role)

    @staticmethod
    async def disable_qr(
        db: AsyncSession,
        table_id: int,
        user: Any,
        role: Any,
    ) -> dict[str, Any]:
        result = await db.execute(
            select(TableQRCode).where(TableQRCode.table_id == table_id)
        )
        qr_code = result.scalar_one_or_none()

        if not qr_code:
            raise HTTPException(
                status_code=404,
                detail="QR code not generated for this table",
            )

        if role.name == "STAFF" and user.client_id != qr_code.client_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if role.name == "CLIENT" and user.id != qr_code.client_id:
            raise HTTPException(status_code=403, detail="Access denied")

        qr_code.is_active = False
        qr_code.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(qr_code)

        qr_url = TableQRService.get_public_qr_url(qr_code.qr_token) if qr_code.qr_token else None

        return {
            "id": qr_code.id,
            "branch_id": qr_code.branch_id,
            "table_id": qr_code.table_id,
            "qr_token": qr_code.qr_token,
            "qr_url": qr_url,
            "is_active": qr_code.is_active,
            "created_at": qr_code.created_at,
            "updated_at": qr_code.updated_at,
        }

    @staticmethod
    async def get_qr_image(
        db: AsyncSession,
        table_id: int,
        user: Any,
        role: Any,
    ):
        qr_info = await TableQRService.get_qr(db, table_id, user, role)
        qr_url = qr_info["qr_url"]

        import qrcode
        from io import BytesIO

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf


class PublicCustomerQRService:

    @staticmethod
    async def resolve_qr_and_start_session(
        db: AsyncSession,
        token: str,
    ) -> dict[str, Any]:
        if not token:
            raise HTTPException(status_code=400, detail="QR token required")

        token_h = hash_token(token)

        qr_res = await db.execute(
            select(TableQRCode)
            .options(
                selectinload(TableQRCode.branch),
                selectinload(TableQRCode.table),
            )
            .where(
                TableQRCode.token_hash == token_h,
                TableQRCode.is_active == True,
            )
        )
        qr_code = qr_res.scalar_one_or_none()

        if not qr_code:
            raise HTTPException(
                status_code=404,
                detail="Invalid or inactive QR code",
            )

        table = qr_code.table
        branch = qr_code.branch

        if not table or not table.is_active:
            raise HTTPException(
                status_code=400,
                detail="Associated table is inactive or unavailable",
            )

        if not branch or branch.status != BranchStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Associated branch is inactive",
            )

        now = datetime.now(timezone.utc)

        session_res = await db.execute(
            select(RestaurantSession).where(
                RestaurantSession.branch_id == branch.id,
                RestaurantSession.table_id == table.id,
                RestaurantSession.status == SessionStatus.ACTIVE.value,
                RestaurantSession.expires_at > now,
            ).order_by(RestaurantSession.id.desc())
        )
        existing_session = session_res.scalars().first()

        # Check if the existing session belongs to a completed/settled dining party
        if existing_session:
            sess_orders_res = await db.execute(
                select(Order).where(Order.restaurant_session_id == existing_session.id)
            )
            sess_orders = list(sess_orders_res.scalars().all())
            if sess_orders:
                active_orders = [o for o in sess_orders if o.status not in ("cancelled", "rejected")]
                if active_orders:
                    # Check if all active orders have a completed bill (bill is clear!)
                    all_bills_completed = True
                    for o in active_orders:
                        b_res = await db.execute(select(Bill).where(Bill.order_id == o.id))
                        b = b_res.scalar_one_or_none()
                        if not b or b.payment_status != PaymentStatus.complete:
                            all_bills_completed = False
                            break
                    if all_bills_completed:
                        # Previous customer's bill has been cleared! Complete the old session so next customer starts fresh.
                        existing_session.status = SessionStatus.COMPLETED.value
                        await db.commit()
                        existing_session = None
                else:
                    # All orders were cancelled/rejected, old session is dead
                    existing_session.status = SessionStatus.COMPLETED.value
                    await db.commit()
                    existing_session = None

        session_token = generate_opaque_token()
        session_token_h = hash_token(session_token)

        if existing_session:
            session = existing_session
            session.session_token_hash = session_token_h
            await db.commit()
            await db.refresh(session)
        else:
            session = RestaurantSession(
                session_token_hash=session_token_h,
                client_id=branch.client_id,
                branch_id=branch.id,
                table_id=table.id,
                customer_id=None,
                status=SessionStatus.ACTIVE.value,
                expires_at=now + timedelta(hours=4),
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

        effective_tax_type = await resolve_branch_tax_type(db, branch.id)

        customer_info = None
        if session.customer_id:
            cust = await db.get(Customer, session.customer_id)
            if cust:
                customer_info = {
                    "id": cust.id,
                    "name": cust.name,
                    "phone": cust.phone,
                    "email": cust.email,
                }

        return {
            "session_token": session_token,
            "branch_name": branch.name,
            "table_name": table.name,
            "floor": table.floor,
            "number_of_seats": table.number_of_seats,
            "currency": branch.currency,
            "tax_type": effective_tax_type,
            "decimal_places": branch.decimal_places or 2,
            "customer": customer_info,
            "_session_id": session.id,
        }

    @staticmethod
    async def get_session_by_token(
        db: AsyncSession,
        session_token: str,
    ) -> RestaurantSession:
        if not session_token:
            raise HTTPException(
                status_code=401,
                detail="Session token missing",
            )

        token_h = hash_token(session_token)
        now = datetime.now(timezone.utc)

        res = await db.execute(
            select(RestaurantSession).where(
                RestaurantSession.session_token_hash == token_h,
                RestaurantSession.status == SessionStatus.ACTIVE.value,
            )
        )
        session = res.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired restaurant session",
            )

        exp = session.expires_at
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                session.status = SessionStatus.EXPIRED.value
                await db.commit()
                raise HTTPException(
                    status_code=401,
                    detail="Restaurant session has expired. Please scan QR again.",
                )

        return session

    @staticmethod
    async def attach_customer(
        db: AsyncSession,
        session: RestaurantSession,
        data: SessionCustomerAttachReq,
    ) -> dict[str, Any]:
        branch = await db.get(Branch, session.branch_id)
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

        clean_name = data.name.strip() if data.name else ""
        clean_phone = data.phone.strip() if data.phone else None
        clean_email = data.email.strip().lower() if data.email else None

        if not clean_name:
            raise HTTPException(
                status_code=400,
                detail="Customer name is required.",
            )

        customer = None
        if clean_phone or clean_email:
            customer, _ = await find_or_create_customer(
                db=db,
                client_id=session.client_id,
                branch_id=session.branch_id,
                branch_name=branch.name,
                name=clean_name,
                phone=clean_phone,
                email=clean_email,
            )
        else:
            # Table QR diner ordering with name only (no phone/email provided)
            session = await db.merge(session)
            if session.customer_id:
                customer = await db.get(Customer, session.customer_id)
                if customer:
                    customer.name = clean_name
                    await db.commit()
                    await db.refresh(customer)

            if not customer:
                guest_phone = f"GUEST-QR-{session.id}"
                stmt = select(Customer).where(
                    Customer.client_id == session.client_id,
                    Customer.phone == guest_phone,
                )
                res = await db.execute(stmt)
                customer = res.scalar_one_or_none()

                if not customer:
                    customer = Customer(
                        client_id=session.client_id,
                        branch_id=session.branch_id,
                        branch_name=branch.name,
                        name=clean_name,
                        phone=guest_phone,
                        email=None,
                        customer_source="QR-Ordering",
                        customer_type=CustomerTypeEnum.NEW,
                        is_vip=False,
                    )
                    db.add(customer)
                    try:
                        await db.commit()
                        await db.refresh(customer)
                    except IntegrityError:
                        await db.rollback()
                        res = await db.execute(stmt)
                        customer = res.scalar_one()

        if not customer:
            raise HTTPException(
                status_code=400,
                detail="Unable to attach customer details.",
            )

        session = await db.merge(session)
        session.customer_id = customer.id
        await db.commit()
        await db.refresh(session)

        # Associate active device tokens from this session to the customer for future engagement
        try:
            from app.accounts.notification.model import DeviceToken
            await db.execute(
                update(DeviceToken)
                .where(DeviceToken.qr_session_id == session.id)
                .values(customer_id=customer.id)
            )
            await db.commit()
        except Exception as dt_err:
            logger.warning(f"Error associating device tokens with customer: {dt_err}")

        display_phone = None if (customer.phone and customer.phone.startswith("GUEST-")) else customer.phone
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "phone": display_phone,
            "email": customer.email,
        }

    @staticmethod
    async def get_public_menu(
        db: AsyncSession,
        session: RestaurantSession,
    ) -> dict[str, Any]:
        branch_id = session.branch_id
        client_id = session.client_id

        cache_key = f"menu:client:{client_id}:branch:{branch_id}"
        cached = await Cache.get(cache_key)
        if cached:
            return cached

        result = await db.execute(
            select(Item)
            .join(
                Pricing,
                (Pricing.item_id == Item.id)
                & (Pricing.branch_id == branch_id)
                & (Pricing.is_active == True),
            )
            .options(
                selectinload(Item.category),
                selectinload(Item.pricings),
            )
            .where(
                Item.client_id == client_id,
                Item.branch_id == branch_id,
                Item.is_active == True,
            )
            .distinct()
            .order_by(Item.id.asc())
        )

        items = result.scalars().unique().all()
        menu: dict[str, list] = {}

        for item in items:
            category_name = (
                item.category.name
                if item.category and item.category.branch_id == branch_id
                else "Others"
            )

            pricing = next(
                (p for p in item.pricings if p.branch_id == branch_id and p.is_active),
                None,
            )

            if pricing:
                base_price = float(pricing.price or 0.0)
                total_price = compute_total_price(pricing)
                discount = float(pricing.discount or 0.0)
                tax = float(pricing.tax or 0.0)
            else:
                base_price = 0.0
                total_price = 0.0
                discount = 0.0
                tax = 0.0

            menu.setdefault(category_name, []).append(
                {
                    "id": item.id,
                    "name": item.name,
                    "price": base_price,
                    "discount": discount,
                    "tax": tax,
                    "total_price": total_price,
                }
            )

        await Cache.set(cache_key, menu, expire=600)
        return menu

    @staticmethod
    async def create_qr_order(
        db: AsyncSession,
        session: RestaurantSession,
        data: PublicOrderCreateReq,
    ) -> Order:
        if not data.items:
            raise HTTPException(
                status_code=400,
                detail="Order must contain at least one item",
            )

        branch = await db.get(Branch, session.branch_id)
        if not branch or branch.status != BranchStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Branch is inactive or not found",
            )

        table = await db.get(Table, session.table_id)
        if not table or not table.is_active:
            raise HTTPException(
                status_code=400,
                detail="Table is inactive or not found",
            )

        if table.branch_id != session.branch_id or table.client_id != session.client_id:
            raise HTTPException(
                status_code=400,
                detail="Table does not match session branch or client",
            )

        customer = None
        if session.customer_id:
            customer = await db.get(Customer, session.customer_id)

        customer_name = customer.name if customer else "QR Guest"
        customer_phone = customer.phone if customer else None

        order = Order(
            client_id=session.client_id,
            branch_id=session.branch_id,
            table_id=session.table_id,
            restaurant_session_id=session.id,
            order_type=OrderType.DINE_IN,
            source=OrderSource.QR,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_id=session.customer_id,
            notes=data.notes,
            status="pending",
        )

        db.add(order)
        await db.flush()

        total_amount = 0.0

        for req_item in data.items:
            if req_item.quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid quantity for item {req_item.item_id}",
                )

            db_item = await db.get(Item, req_item.item_id)
            if not db_item or not db_item.is_active:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {req_item.item_id} not found or inactive",
                )

            if db_item.branch_id != session.branch_id or db_item.client_id != session.client_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Item {db_item.name} does not belong to this branch",
                )

            pricing = await resolve_pricing(
                db=db,
                db_item=db_item,
                client_id=session.client_id,
                branch_id=session.branch_id,
            )

            snap = order_item_line_snapshot(pricing, req_item.quantity)

            order_item = OrderItem(
                order_id=order.id,
                item_id=db_item.id,
                customer_id=session.customer_id,
                quantity=req_item.quantity,
                unit_price=snap["unit_price"],
                discount_percent=snap["discount_percent"],
                tax_percent=snap["tax_percent"],
                subtotal=snap["subtotal"],
                tax_amount=snap["tax_amount"],
                total_price=snap["total_price"],
                order_status="pending",
            )

            db.add(order_item)
            total_amount += snap["total_price"]

        order.total_amount = round(total_amount, 2)

        # Mark table occupied when order is created
        table.status = TableStatus.occupied
        await Cache.delete(f"tables:branch:{table.branch_id}")

        await db.commit()

        # Eager load order_items with selectinload to prevent MissingGreenlet in async context
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.order_items))
            .where(Order.id == order.id)
        )
        order = result.scalar_one()

        # Trigger FCM push notification to kitchen staff and QR session device
        try:
            from app.accounts.notification.service import NotificationService
            await NotificationService.send_new_order_to_kitchen(db, order)
        except Exception as notif_err:
            logger.warning(f"FCM notification failed on create_qr_order: {notif_err}")

        return order

    @staticmethod
    async def initiate_payment(
        db: AsyncSession,
        session: RestaurantSession,
        order_id: int,
    ) -> dict[str, Any]:
        res = await db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.restaurant_session_id == session.id,
            )
        )
        order = res.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found for this session",
            )

        bill_res = await db.execute(
            select(Bill).where(Bill.order_id == order.id)
        )
        bill = bill_res.scalar_one_or_none()

        branch = await db.get(Branch, session.branch_id)

        if not bill:
            calculated = _calculate_bill_totals(
                subtotal=order.total_amount,
                tax_total=0.0,
                service_charge_percent=0.0,
                discount_amount=0.0,
                offer_discount=0.0,
                round_off_enabled=True,
            )

            bill = Bill(
                order_id=order.id,
                client_id=session.client_id,
                branch_id=session.branch_id,
                customer_id=session.customer_id,
                invoice_no=f"INV-QR-{secrets.token_hex(4).upper()}",
                order_type=order.order_type,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                payment_status=PaymentStatus.pending,
                subtotal=calculated["subtotal"],
                tax_type=branch.tax_type if branch else "GST",
                grand_total=calculated["grand_total"],
                final_amount=calculated["final_amount"],
                due_amount=calculated["final_amount"],
                paid_amount=0.0,
            )
            db.add(bill)
            await db.commit()
            await db.refresh(bill)

        if bill.payment_status == PaymentStatus.complete:
            raise HTTPException(
                status_code=400,
                detail="Bill is already paid",
            )

        razorpay_order = create_razorpay_order(
            amount=bill.final_amount,
            bill_id=bill.id,
            invoice_no=bill.invoice_no,
        )

        return {
            "order_id": order.id,
            "bill_id": bill.id,
            "invoice_no": bill.invoice_no,
            "razorpay_order_id": razorpay_order["id"],
            "razorpay_key_id": RAZORPAY_KEY_ID or "",
            "amount": bill.final_amount,
            "amount_paise": razorpay_order["amount"],
            "currency": razorpay_order["currency"],
        }

    @staticmethod
    async def verify_payment(
        db: AsyncSession,
        session: RestaurantSession,
        data: RazorpayPaymentVerifyReq,
    ) -> dict[str, Any]:
        verify_razorpay_payment(
            razorpay_order_id=data.razorpay_order_id,
            razorpay_payment_id=data.razorpay_payment_id,
            razorpay_signature=data.razorpay_signature,
        )

        bill_res = await db.execute(
            select(Bill)
            .where(
                Bill.id == data.bill_id,
                Bill.branch_id == session.branch_id,
            )
            .with_for_update()
        )
        bill = bill_res.scalar_one_or_none()

        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")

        # Idempotency check: If bill already completed, return clean status without double processing
        if bill.payment_status == PaymentStatus.complete:
            payment_res = await db.execute(
                select(Payment).where(Payment.bill_id == bill.id)
            )
            payment = payment_res.scalars().first()
            return {
                "status": "success",
                "message": "Payment already verified and completed",
                "bill_id": bill.id,
                "order_id": bill.order_id,
                "payment_id": payment.id if payment else 0,
                "order_status": "confirmed",
            }

        payment_payload = PaymentCreate(
            bill_id=bill.id,
            payments=[
                PaymentItem(
                    payment_method=PaymentMethod.razorpay,
                    payment_amount=bill.final_amount,
                )
            ],
            payment_reference=data.razorpay_payment_id,
            notes=f"Razorpay QR Dine-In Payment {data.razorpay_payment_id}",
            use_wallet=False,
        )

        payment = await make_payment_service(
            db=db,
            data=payment_payload,
            razorpay_verified=True,
        )

        order_res = await db.execute(
            select(Order)
            .options(selectinload(Order.order_items))
            .where(Order.id == bill.order_id)
        )
        order = order_res.scalar_one_or_none()
        if order:
            order.status = "confirmed"
            for oi in order.order_items:
                oi.order_status = "confirmed"

        branch = await db.get(Branch, session.branch_id)
        branch_name = branch.name if branch else ""

        if bill.customer_id:
            cust = await db.get(Customer, bill.customer_id)
            c_name = cust.name if cust else bill.customer_name
            c_phone = cust.phone if cust else bill.customer_phone
            c_email = cust.email if cust else None
        else:
            c_name = bill.customer_name
            c_phone = bill.customer_phone
            c_email = None

        await handle_customer_and_visit(
            db=db,
            client_id=session.client_id,
            branch_id=session.branch_id,
            branch_name=branch_name,
            order_id=bill.order_id,
            bill_id=bill.id,
            total_amount=bill.grand_total,
            discount=bill.discount_amount + bill.offer_discount,
            tax=bill.tax_total,
            payment_method="razorpay",
            visit_type="dine_in",
            customer_name=c_name,
            customer_phone=c_phone,
            customer_email=c_email,
        )

        # Mark table session completed and free table
        session.status = SessionStatus.COMPLETED.value
        tbl = await db.get(Table, session.table_id)
        if tbl:
            tbl.status = TableStatus.available

        await db.commit()

        # Trigger payment success and bill completed FCM notifications safely
        try:
            from app.accounts.notification.service import NotificationService
            if order:
                await NotificationService.send_payment_success(db, order, bill)
            await NotificationService.send_bill_completed(db, bill)
        except Exception as pay_notif_err:
            logger.warning(f"FCM payment notification failed: {pay_notif_err}")

        return {
            "status": "success",
            "message": "Payment verified and order confirmed",
            "bill_id": bill.id,
            "order_id": bill.order_id,
            "payment_id": payment.id,
            "order_status": "confirmed",
        }
