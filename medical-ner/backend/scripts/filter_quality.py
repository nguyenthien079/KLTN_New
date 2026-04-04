import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Article


async def filter_low_quality():
    """Remove low quality articles"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Article))
        articles = result.scalars().all()

        removed_count = 0
        for article in articles:
            if not article.clean_text:
                await db.delete(article)
                removed_count += 1
                continue

            if (
                len(article.clean_text) < 200 or
                len(article.clean_text) > 50000 or
                article.clean_text.count(' ') < 20
            ):
                await db.delete(article)
                removed_count += 1

        await db.commit()
        print(f"Removed {removed_count} low quality articles")
        print(f"Remaining: {len(articles) - removed_count}")


if __name__ == "__main__":
    asyncio.run(filter_low_quality())
