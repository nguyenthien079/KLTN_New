import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.pipeline.pipeline import MedicalTextPipeline


async def main():
    async with AsyncSessionLocal() as db:
        pipeline = MedicalTextPipeline(db)
        stats = await pipeline.process_all_articles()

        print("\n" + "="*60)
        print("PIPELINE COMPLETED")
        print("="*60)
        print(f"Articles processed: {stats['articles_processed']}")
        print(f"Total sentences:    {stats['total_sentences']}")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
