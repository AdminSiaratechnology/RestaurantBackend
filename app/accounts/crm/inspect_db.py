"""
Script to inspect database state and sync any missing CustomerVisitHistory entries.
"""

import asyncio
import app.db.base  # noqa
from sqlalchemy import select, func
from app.db.config import async_session
from app.accounts.bill.model import Bill
from app.accounts.customer.model import Customer
from app.accounts.crm.customer_history.model import CustomerVisitHistory
from app.accounts.crm.customer_history.checkout_service import handle_customer_and_visit
from app.accounts.branch.model import Branch


async def inspect_and_sync_db():
    print("=== INSPECTING DATABASE STATE ===")
    async with async_session() as db:
        bill_count = (await db.execute(select(func.count(Bill.id)))).scalar() or 0
        visit_count = (await db.execute(select(func.count(CustomerVisitHistory.id)))).scalar() or 0
        customer_count = (await db.execute(select(func.count(Customer.id)))).scalar() or 0

        print(f"Total Bills in Database: {bill_count}")
        print(f"Total CustomerVisitHistory Records: {visit_count}")
        print(f"Total Customers Registered: {customer_count}")

        # Fetch all bills
        bills = (await db.execute(select(Bill))).scalars().all()
        print(f"\nFound {len(bills)} bill records:")
        for b in bills:
            print(f"  - Bill ID #{b.id}: Order #{b.order_id}, Invoice: '{b.invoice_no}', PaymentStatus: '{b.payment_status}', Phone: '{b.customer_phone}', GrandTotal: Rs.{b.grand_total}")

            # Check if visit history exists for this bill
            existing_visit = (await db.execute(
                select(CustomerVisitHistory).where(CustomerVisitHistory.bill_id == b.id)
            )).scalar_one_or_none()

            if not existing_visit:
                print(f"    [Syncing Missing Visit History for Bill #{b.id}]...")
                branch = await db.get(Branch, b.branch_id)
                customer = await handle_customer_and_visit(
                    db=db,
                    client_id=b.client_id,
                    branch_id=b.branch_id,
                    branch_name=branch.name if branch else "Main Branch",
                    order_id=b.order_id,
                    bill_id=b.id,
                    total_amount=b.final_amount or b.grand_total,
                    discount=(b.discount_amount or 0) + (b.offer_discount or 0),
                    tax=b.tax_total or 0,
                    payment_method=b.payment_method or "Cash",
                    table_name=None,
                    visit_type=b.order_type or "Dine-In",
                    customer_name=b.customer_name or "Walk-in Guest",
                    customer_phone=b.customer_phone,
                )
                if customer:
                    b.customer_id = customer.id

        await db.commit()

        # Re-check count
        new_visit_count = (await db.execute(select(func.count(CustomerVisitHistory.id)))).scalar() or 0
        print(f"\n=== SYNC COMPLETE ===")
        print(f"New CustomerVisitHistory Count: {new_visit_count}")


if __name__ == "__main__":
    asyncio.run(inspect_and_sync_db())
