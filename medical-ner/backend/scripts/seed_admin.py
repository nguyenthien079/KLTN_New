"""Run once: python scripts/seed_admin.py"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth import hash_password


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Admin already exists")
            return

        user = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            display_name="Administrator",
            role="admin",
        )
        db.add(user)
        await db.commit()
        print("Created admin user: admin / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
