"""
Persist discovered URLs from JSON files into PostgreSQL.

Reads every domain file under data/listsite/ and upserts the domain
and its URLs into the discovered_domains / discovered_urls tables.

Usage:
    python scripts/persist_latest_to_db.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.crawler.domain_store import list_domains, load_urls, save_urls_to_db
from app.database import AsyncSessionLocal


async def main() -> None:
    domains = list_domains()
    if not domains:
        print("No domains found. Run discover_sites.py first.")
        sys.exit(0)

    print(f"Persisting {len(domains)} domain(s) to PostgreSQL...\n")

    async with AsyncSessionLocal() as db:
        for domain in domains:
            urls = load_urls(domain)
            await save_urls_to_db(domain, urls, db)
            print(f"  ✓ {domain}  ({len(urls)} URLs)")

    print(f"\nDone. {len(domains)} domain(s) persisted.")


if __name__ == "__main__":
    asyncio.run(main())
