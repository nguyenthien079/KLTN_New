import asyncio
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.config import config
from app.crawler.extractor import HTMLExtractor
from app.crawler.deduplicator import Deduplicator
from app.models import Article, CrawlStatus


class MedicalCrawler:
    """Crawl medical websites and save articles to database"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.extractor = HTMLExtractor()
        self.deduplicator = Deduplicator(threshold=config.similarity_threshold)
        self.visited_urls: Set[str] = set()
        self.crawled_articles: List[Dict] = []

    async def crawl_site(
        self,
        start_url: str,
        max_pages: int = 100
    ) -> List[Article]:
        """Crawl a medical website starting from start_url"""
        domain = urlparse(start_url).netloc
        queue = [start_url]
        crawled = []

        print(f"[Crawler] Start: {start_url} | max_pages={max_pages}")

        while queue and len(crawled) < max_pages:
            url = queue.pop(0)

            if url in self.visited_urls:
                continue

            self.visited_urls.add(url)

            # Fetch HTML
            html = await self.extractor.fetch_html(url)
            if not html:
                print(f"  [SKIP] Cannot fetch: {url}")
                continue

            # Extract clean text
            extracted = self.extractor.extract_clean_text(html)

            # Skip very short articles
            if extracted["char_count"] < 100:
                print(f"  [SKIP] Too short ({extracted['char_count']} chars): {url}")
                continue

            article_data = {
                "url": url,
                "title": extracted["title"],
                "raw_html": html,
                "clean_text": extracted["clean_text"],
                "char_count": extracted["char_count"],
                "source_domain": domain,
                "content_hash": self.deduplicator.compute_hash(extracted["clean_text"]),
                "status": CrawlStatus.COMPLETED
            }

            crawled.append(article_data)
            print(f"  [{len(crawled):>3}/{max_pages}] OK ({extracted['char_count']:>6} chars) | {extracted['title'][:60] or url}")

            # Find more links (same domain only)
            soup = BeautifulSoup(html, 'lxml')
            new_links = 0
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])
                if self._is_valid_url(next_url, domain):
                    queue.append(next_url)
                    new_links += 1

            print(f"       Queue: {len(queue)} URLs | New links found: {new_links}")

            # Rate limiting
            await asyncio.sleep(config.request_delay)

        print(f"[Crawler] Done crawling. Saving {len(crawled)} articles to DB...")
        saved = await self._save_articles(crawled)
        print(f"[Crawler] Saved {len(saved)} new articles (skipped {len(crawled)-len(saved)} duplicates)")
        return saved

    def _is_valid_url(self, url: str, target_domain: str) -> bool:
        """Check if URL is valid for crawling"""
        parsed = urlparse(url)

        if parsed.netloc != target_domain:
            return False

        url_lower = url.lower()
        if not any(kw in url_lower for kw in config.medical_keywords):
            return False

        if url in self.visited_urls:
            return False

        return True

    async def _save_articles(self, articles_data: List[Dict]) -> List[Article]:
        """Save articles to database with duplicate detection"""
        saved_articles = []

        for data in articles_data:
            # Check duplicate by URL or content hash
            result = await self.db.execute(
                select(Article).where(
                    (Article.url == data["url"]) |
                    (Article.content_hash == data["content_hash"])
                )
            )
            if result.first():
                continue

            article = Article(**data)
            self.db.add(article)
            saved_articles.append(article)

        await self.db.commit()
        return saved_articles
