from sqlalchemy import text
from app.db.config import engine

async def create_db_indexes():
    print("STARTING INDEX CREATION")
    queries = [
        # ── Menu items ──────────────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_items_branch_id ON items (branch_id);",
        "CREATE INDEX IF NOT EXISTS ix_items_category_id ON items (category_id);",
        "CREATE INDEX IF NOT EXISTS ix_items_branch_category_id ON items (branch_id, category_id);",
        "CREATE INDEX IF NOT EXISTS ix_items_name ON items (name);",
        # ── Inventory items ─────────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_inventory_branch_id ON inventory_items (branch_id);",
        "CREATE INDEX IF NOT EXISTS ix_inventory_godown_id ON inventory_items (godown_id);",
        "CREATE INDEX IF NOT EXISTS ix_inventory_branch_godown ON inventory_items (branch_id, godown_id);",
        "CREATE INDEX IF NOT EXISTS ix_inventory_status ON inventory_items (status);",
        "CREATE INDEX IF NOT EXISTS ix_inventory_branch_status ON inventory_items (branch_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_inventory_name ON inventory_items (name);",
        "CREATE INDEX IF NOT EXISTS ix_inventory_id ON inventory_items (id);",
        # ── Offers ──────────────────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_offers_branch_id ON offers (branch_id);",
        "CREATE INDEX IF NOT EXISTS ix_offers_is_active ON offers (is_active);",
        "CREATE INDEX IF NOT EXISTS ix_offers_valid_from ON offers (valid_from);",
        "CREATE INDEX IF NOT EXISTS ix_offers_valid_to ON offers (valid_to);",
        "CREATE INDEX IF NOT EXISTS ix_offers_branch_active ON offers (branch_id, is_active);",
        "CREATE INDEX IF NOT EXISTS ix_offers_id ON offers (id);",
        # ── Orders & Order Items ────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_orders_branch_status_created ON orders (branch_id, status, created_at);",
        "CREATE INDEX IF NOT EXISTS ix_orders_client_branch ON orders (client_id, branch_id);",
        "CREATE INDEX IF NOT EXISTS ix_orders_table_status ON orders (table_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_orders_customer_id ON orders (customer_id);",
        "CREATE INDEX IF NOT EXISTS ix_orders_session_id ON orders (restaurant_session_id);",
        "CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders (created_at);",
        "CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id);",
        "CREATE INDEX IF NOT EXISTS ix_order_items_item_id ON order_items (item_id);",
        "CREATE INDEX IF NOT EXISTS ix_order_items_order_status ON order_items (order_id, order_status);",
        # ── Bills & Payments ────────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_bills_branch_payment_created ON bills (branch_id, payment_status, created_at);",
        "CREATE INDEX IF NOT EXISTS ix_bills_order_id ON bills (order_id);",
        "CREATE INDEX IF NOT EXISTS ix_bills_customer_id ON bills (customer_id);",
        "CREATE INDEX IF NOT EXISTS ix_bills_invoice_no ON bills (invoice_no);",
        "CREATE INDEX IF NOT EXISTS ix_payments_bill_id ON payments (bill_id);",
        "CREATE INDEX IF NOT EXISTS ix_payments_branch_method ON payments (branch_id, payment_method);",
        # ── Customers & CRM Visit History ───────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_cust_visits_cust_branch ON customer_visit_history (customer_id, branch_id);",
        "CREATE INDEX IF NOT EXISTS ix_cust_visits_branch_created ON customer_visit_history (branch_id, created_at);",
        "CREATE INDEX IF NOT EXISTS ix_cust_visits_bill_id ON customer_visit_history (bill_id);",
        "CREATE INDEX IF NOT EXISTS ix_cust_visits_order_id ON customer_visit_history (order_id);",
        "CREATE INDEX IF NOT EXISTS ix_customers_client_phone ON customers (client_id, phone);",
        "CREATE INDEX IF NOT EXISTS ix_customers_client_email ON customers (client_id, email);",
        "CREATE INDEX IF NOT EXISTS ix_customers_branch_id ON customers (branch_id);",
        # ── Tables & QR Sessions ────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_tables_branch_status ON tables (branch_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_tables_client_branch ON tables (client_id, branch_id);",
        "CREATE INDEX IF NOT EXISTS ix_sessions_table_status ON restaurant_sessions (table_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_sessions_branch_status ON restaurant_sessions (branch_id, status);",
        # ── Pricing ─────────────────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS ix_pricing_item_branch_active ON pricings (item_id, branch_id, is_active);",
        "CREATE INDEX IF NOT EXISTS ix_pricing_client_item_active ON pricings (client_id, item_id, is_active);",
    ]
    async with engine.begin() as conn:
        for q in queries:
            try:
                await conn.execute(text(q))
                print(f"Success: {q}")
            except Exception as e:
                print(f"Error running '{q}': {e}")
    print("INDEX CREATION FINISHED")
