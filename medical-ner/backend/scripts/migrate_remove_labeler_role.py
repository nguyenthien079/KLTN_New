"""Run once: migrate all users with role='labeler' to role='chuyen_gia'.
Also clears stale role_requests that targeted chuyen_gia (now targeting admin).

Usage: python scripts/migrate_remove_labeler_role.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


async def migrate():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE users SET role = 'chuyen_gia' WHERE role = 'labeler'")
        )
        print(f"Updated {result.rowcount} labeler(s) → chuyen_gia")

        result2 = await conn.execute(
            text(
                "UPDATE role_requests SET requested_role = 'admin' "
                "WHERE requested_role = 'chuyen_gia' AND status = 'pending'"
            )
        )
        print(f"Updated {result2.rowcount} pending role_request(s): chuyen_gia → admin")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(migrate())
