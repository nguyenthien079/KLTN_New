"""
One-time migration: create new tables (users) and add missing columns to existing tables.
Run: python scripts/migrate_add_auth_columns.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, Base

# Import all models so Base.metadata knows about them
from app.models import Article, Sentence, Entity, KnowledgeMap, Correction, User  # noqa


async def migrate():
    async with engine.begin() as conn:
        # Step 1: create any missing tables (users, etc.) without touching existing ones
        await conn.run_sync(Base.metadata.create_all)
        print("Step 1: Tables created (skipped existing).")

        # Step 2: add labeler_id to corrections (nullable FK to users)
        await conn.execute(text("""
            ALTER TABLE corrections
            ADD COLUMN IF NOT EXISTS labeler_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL;
        """))
        print("Step 2: corrections.labeler_id added.")

        # Step 3: add status to corrections
        await conn.execute(text("""
            ALTER TABLE corrections
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending_review';
        """))
        print("Step 3: corrections.status added.")

        print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
