"""
One-time migration: add missing columns to existing tables.
Run: python scripts/migrate_add_auth_columns.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine


async def migrate():
    async with engine.begin() as conn:
        # Add labeler_id to corrections (nullable FK)
        await conn.execute(__import__('sqlalchemy').text("""
            ALTER TABLE corrections
            ADD COLUMN IF NOT EXISTS labeler_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL;
        """))

        # Add status to corrections
        await conn.execute(__import__('sqlalchemy').text("""
            ALTER TABLE corrections
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending_review';
        """))

        print("Migration complete: corrections.labeler_id + corrections.status added.")


if __name__ == "__main__":
    asyncio.run(migrate())
