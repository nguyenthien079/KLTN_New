import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.crawler.crawler import MedicalCrawler

# Site configurations
SITES = [
    {
        "name": "Sức Khỏe Đời Sống",
        "urls": [
            "https://suckhoedoisong.vn/benh",
            "https://suckhoedoisong.vn/thuoc",
            "https://suckhoedoisong.vn/trieu-chung"
        ],
        "max_pages": 300
    },
    {
        "name": "Vinmec",
        "urls": [
            "https://www.vinmec.com/vie/benh",
            "https://www.vinmec.com/vie/thuoc"
        ],
        "max_pages": 300
    },
    {
        "name": "Hello Bacsi",
        "urls": [
            "https://hellobacsi.com/benh-ly-thuong-gap",
            "https://hellobacsi.com/thuoc"
        ],
        "max_pages": 200
    },
    {
        "name": "Bệnh Viện Tâm Anh",
        "urls": [
            "https://tamanhhospital.vn/benh-thuong-gap",
            "https://tamanhhospital.vn/dieu-tri"
        ],
        "max_pages": 200
    },
    {
        "name": "Nhà Thuốc Long Châu",
        "urls": [
            "https://nhathuoclongchau.com.vn/benh",
            "https://nhathuoclongchau.com.vn/thuoc"
        ],
        "max_pages": 250
    }
]


async def crawl_all_sites():
    """Crawl tất cả các site"""
    total_articles = 0

    async with AsyncSessionLocal() as db:
        crawler = MedicalCrawler(db)

        for site in SITES:
            print(f"\n{'='*60}")
            print(f"Crawling: {site['name']}")
            print(f"{'='*60}\n")

            for url in site['urls']:
                print(f"Starting from: {url}")
                articles = await crawler.crawl_site(url, max_pages=site['max_pages'])
                total_articles += len(articles)
                print(f"Crawled {len(articles)} articles from {url}")

                # Delay between URLs
                await asyncio.sleep(5)

    print(f"\n{'='*60}")
    print(f"TOTAL ARTICLES CRAWLED: {total_articles}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(crawl_all_sites())
