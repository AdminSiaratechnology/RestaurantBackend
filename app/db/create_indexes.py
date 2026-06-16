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
    ]
    async with engine.begin() as conn:
        for q in queries:
            try:
                await conn.execute(text(q))
                print(f"Success: {q}")
            except Exception as e:
                print(f"Error running '{q}': {e}")
    print("INDEX CREATION FINISHED")
