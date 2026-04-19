"""
Backend CLI for site discovery.

Usage:
    python scripts/discover_sites.py <url> [<url2> ...]

Discovers all URLs for each given domain and saves them to:
    data/listsite/{domain}/{domain}.json
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.crawler.discovery import SiteDiscovery
from app.crawler.domain_store import normalize_domain, save_urls


async def discover_site(url: str) -> None:
    domain = normalize_domain(url)
    print(f"\n{'='*60}")
    print(f"Discovering: {url}  →  domain: {domain}")
    print(f"{'='*60}")

    discovery = SiteDiscovery()

    def on_progress(count: int, found_url: str):
        print(f"  [{count}] {found_url}")

    urls = await discovery.discover(url, on_progress=on_progress)
    save_urls(domain, urls)
    print(f"\nSaved {len(urls)} URLs → data/listsite/{domain}/{domain}.json")


async def main(start_urls: list[str]) -> None:
    for url in start_urls:
        await discover_site(url)
        await asyncio.sleep(2)

    print(f"\nDiscovery complete. Processed {len(start_urls)} site(s).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/discover_sites.py <url> [<url2> ...]")
        sys.exit(1)

    asyncio.run(main(sys.argv[1:]))
