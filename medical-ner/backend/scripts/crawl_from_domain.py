"""
Backend CLI for crawling a domain whose URLs were previously discovered.

Usage:
    # List available domains
    python scripts/crawl_from_domain.py --list

    # Crawl a specific domain
    python scripts/crawl_from_domain.py <domain>

    # Example
    python scripts/crawl_from_domain.py suckhoedoisong.vn
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.crawler.domain_store import list_domains, load_urls
from app.database import AsyncSessionLocal
from app.crawler.crawler import MedicalCrawler


async def crawl_domain(domain: str) -> None:
    urls = load_urls(domain)
    if not urls:
        print(f"No URLs found for domain '{domain}'. Run discover_sites.py first.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Crawling domain: {domain}  ({len(urls)} URLs)")
    print(f"{'='*60}\n")

    async with AsyncSessionLocal() as db:
        crawler = MedicalCrawler(db)
        total = len(urls)

        def on_progress(processed: int, saved: int, url: str, title: str, result: str):
            label = {"ok": "✓", "fail": "✗ FAIL", "skip": "— SKIP"}.get(result, result)
            title_part = f" — {title[:60]}" if title else ""
            print(f"  [{processed}/{total}] {label} {url}{title_part}")

        articles = await crawler.crawl_url_list(urls, on_progress=on_progress)
        print(f"\nDone. Saved {len(articles)} new articles for {domain}.")


def main() -> None:
    domains = list_domains()

    if "--list" in sys.argv or "-l" in sys.argv:
        if not domains:
            print("No domains found. Run discover_sites.py first.")
        else:
            print("Available domains:")
            for d in domains:
                urls = load_urls(d)
                print(f"  {d}  ({len(urls)} URLs)")
        return

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/crawl_from_domain.py --list")
        print("  python scripts/crawl_from_domain.py <domain>")
        if domains:
            print("\nAvailable domains:", ", ".join(domains))
        sys.exit(1)

    domain = sys.argv[1]
    if domain not in domains:
        print(f"Domain '{domain}' not found.")
        if domains:
            print("Available:", ", ".join(domains))
        sys.exit(1)

    asyncio.run(crawl_domain(domain))


if __name__ == "__main__":
    main()
