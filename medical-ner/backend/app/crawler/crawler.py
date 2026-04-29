import asyncio
from typing import Callable, Dict, List, Optional, Set
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

    async def crawl_url_list(
        self,
        urls: List[str],
        on_progress: Optional[Callable[[int, int, str, str, str], None]] = None
    ) -> List[Article]:
        """Crawl an explicit list of URLs (no further discovery).
        on_progress(processed, saved, url, title, result)
          processed — total URLs attempted so far (drives the progress bar)
          saved     — articles successfully fetched & queued for DB save
          url       — current URL
          title     — extracted title (empty string if unavailable)
          result    — 'ok' | 'skip' | 'fail'
        """
        crawled = []
        total = len(urls)
        processed = 0
        print(f"[Crawler] List mode: {total} URLs to crawl")

        for url in urls:
            processed += 1

            if url in self.visited_urls:
                if on_progress:
                    on_progress(processed, len(crawled), url, "", "skip")
                print(f"  [{processed:>4}/{total}] SKIP (already visited): {url}")
                continue

            self.visited_urls.add(url)

            html = await self.extractor.fetch_html(url)
            if not html:
                if on_progress:
                    on_progress(processed, len(crawled), url, "", "fail")
                print(f"  [{processed:>4}/{total}] FAIL (cannot fetch): {url}")
                continue

            extracted = self.extractor.extract_clean_text(html)
            if extracted["char_count"] < 100:
                if on_progress:
                    on_progress(processed, len(crawled), url, extracted.get("title", ""), "skip")
                print(f"  [{processed:>4}/{total}] SKIP (too short, {extracted['char_count']} chars): {url}")
                continue

            domain = urlparse(url).netloc
            article_data = {
                "url": url,
                "title": extracted["title"],
                "raw_html": html,
                "clean_text": extracted["clean_text"],
                "char_count": extracted["char_count"],
                "source_domain": domain,
                "content_hash": self.deduplicator.compute_hash(extracted["clean_text"]),
                "status": CrawlStatus.COMPLETED,
            }
            crawled.append(article_data)
            if on_progress:
                on_progress(processed, len(crawled), url, extracted.get("title", ""), "ok")
            print(f"  [{processed:>4}/{total}] OK  ({extracted['char_count']:>6} chars): {extracted['title'][:60] or url}")

            await asyncio.sleep(config.request_delay)

        print(f"[Crawler] List crawl done. Saving {len(crawled)} articles to DB...")
        saved = await self._save_articles(crawled)
        print(f"[Crawler] Saved {len(saved)} new articles (skipped {len(crawled)-len(saved)} duplicates)")
        return saved

    async def crawl_site(
        self,
        start_url: str,
        max_pages: Optional[int] = None,
        on_progress: Optional[Callable[[int, str, str], None]] = None
    ) -> List[Article]:
        """Crawl a medical website starting from start_url"""
        domain = urlparse(start_url).netloc
        queue = [start_url]
        crawled = []

        print(f"[Crawler] Start: {start_url} | max_pages={max_pages or 'unlimited'}")

        while queue and (max_pages is None or len(crawled) < max_pages):
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
            if on_progress:
                on_progress(len(crawled), url, extracted.get("title", ""))
            print(f"  [{len(crawled):>3}] OK ({extracted['char_count']:>6} chars) | {extracted['title'][:60] or url}")

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
            for field in ("raw_html", "clean_text", "title"):
                if isinstance(data.get(field), str):
                    data[field] = data[field].replace("\x00", "")

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
