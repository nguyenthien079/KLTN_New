import asyncio
from app.database import AsyncSessionLocal
from app.crawler.crawler import MedicalCrawler

async def test():
    async with AsyncSessionLocal() as db:
        crawler = MedicalCrawler(db)
        articles = await crawler.crawl_site('https://suckhoedoisong.vn/benh', max_pages=10)
        print(f'Crawled: {len(articles)} articles')

asyncio.run(test())
