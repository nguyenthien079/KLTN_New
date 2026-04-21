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
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.crawler.domain_store import list_domains, load_urls
from app.database import AsyncSessionLocal
from app.crawler.crawler import MedicalCrawler


def sanitize_filename(filename: str) -> str:
    """Sanitize filename - remove invalid characters"""
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    filename = filename.strip('. ')
    return filename[:255]  # Max filename length


def save_article_to_file(domain: str, title: str, clean_text: str) -> None:
    """Save article text to file organized by domain"""
    base_path = Path(__file__).parent.parent / "data" / "domain"
    domain_path = base_path / domain
    
    # Create directory structure
    domain_path.mkdir(parents=True, exist_ok=True)
    
    # Sanitize title and save
    safe_title = sanitize_filename(title) if title else "untitled"
    file_path = domain_path / f"{safe_title}.txt"
    
    # If file exists, append a number
    if file_path.exists():
        counter = 1
        base_name = safe_title
        while file_path.exists():
            safe_title = f"{base_name}_{counter}"
            file_path = domain_path / f"{safe_title}.txt"
            counter += 1
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(clean_text)
    except Exception as e:
        print(f"    ⚠️  Failed to save text file: {e}")


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
        
        # Save articles to text files
        for article in articles:
            if article.clean_text:
                save_article_to_file(article.source_domain, article.title or "untitled", article.clean_text)
        
        print(f"\nDone. Saved {len(articles)} new articles for {domain}.")
        print(f"Text files saved to: data/domain/{domain}/")


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
