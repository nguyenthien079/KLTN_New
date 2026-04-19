import json
import os
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

_DATA_ROOT = Path(__file__).parent.parent.parent / "data" / "listsite"


def normalize_domain(url: str) -> str:
    """Extract and normalize domain from URL. Strips www. prefix."""
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _domain_dir(domain: str) -> Path:
    return _DATA_ROOT / domain


def _domain_file(domain: str) -> Path:
    return _domain_dir(domain) / f"{domain}.json"


def save_urls(domain: str, urls: List[str]) -> None:
    """Persist URLs for a domain, merging with any existing entries."""
    domain_dir = _domain_dir(domain)
    domain_dir.mkdir(parents=True, exist_ok=True)

    file_path = _domain_file(domain)
    existing: List[str] = []
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            existing = data.get("urls", [])
        except (json.JSONDecodeError, KeyError):
            existing = []

    merged = sorted(set(existing) | set(urls))
    file_path.write_text(
        json.dumps({"domain": domain, "urls": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_urls(domain: str) -> List[str]:
    """Load URLs for a domain. Returns empty list if not found."""
    file_path = _domain_file(domain)
    if not file_path.exists():
        return []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data.get("urls", [])
    except (json.JSONDecodeError, KeyError):
        return []


def list_domains() -> List[str]:
    """List all domains that have a stored JSON file."""
    if not _DATA_ROOT.exists():
        return []
    return sorted(
        d.name
        for d in _DATA_ROOT.iterdir()
        if d.is_dir() and _domain_file(d.name).exists()
    )


async def save_urls_to_db(domain: str, urls: List[str], session: AsyncSession) -> None:
    """Upsert domain + its URLs into PostgreSQL. No-op if already present."""
    from app.models.discovered_url import DiscoveredDomain, DiscoveredUrl

    # Upsert domain row; use DO UPDATE so RETURNING always gives us the id.
    domain_stmt = (
        pg_insert(DiscoveredDomain)
        .values(domain=domain)
        .on_conflict_do_update(
            index_elements=["domain"],
            set_={"domain": domain},
        )
        .returning(DiscoveredDomain.id)
    )
    result = await session.execute(domain_stmt)
    domain_id: int = result.scalar_one()

    if urls:
        url_stmt = (
            pg_insert(DiscoveredUrl)
            .values([{"domain_id": domain_id, "url": u} for u in urls])
            .on_conflict_do_nothing(
                constraint="uq_discovered_urls_domain_url"
            )
        )
        await session.execute(url_stmt)

    await session.commit()
