import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import AnyHttpUrl, BaseModel

router = APIRouter()

# In-memory job tracking (production: use Redis/Celery)
crawl_jobs: dict = {}
discovery_jobs: dict = {}


class DiscoverRequest(BaseModel):
    url: AnyHttpUrl


class DiscoverStatusResponse(BaseModel):
    job_id: str
    status: str
    url_count: int
    logs: list[str] = []
    urls: list[str] = []
    error: str | None = None


class CrawlStartRequest(BaseModel):
    url: str
    max_pages: Optional[int] = None
    urls: Optional[list[str]] = None  # explicit URL list from discovery


class CrawlStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: dict  # {pages_crawled, total_urls (or None)}
    logs: list[str] = []
    error: str | None = None


@router.post("/start")
async def start_crawl(request: CrawlStartRequest):
    """Start a background crawl job"""
    job_id = str(uuid.uuid4())

    crawl_jobs[job_id] = {
        "status": "running",
        "url": request.url,
        "pages_crawled": 0,       # articles successfully fetched
        "urls_processed": 0,      # total URLs attempted (drives progress bar)
        "total_urls": len(request.urls) if request.urls else None,
        "logs": []
    }

    # asyncio.create_task schedules the coroutine independently of this request —
    # it will keep running even if the client disconnects or navigates away.
    asyncio.create_task(run_crawl_job(job_id, request.url, request.max_pages, request.urls))

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Crawl job started for {request.url}"
    }


@router.get("/status/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: str):
    """Get status of a crawl job"""
    if job_id not in crawl_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = crawl_jobs[job_id]
    return CrawlStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress={
            "pages_crawled": job.get("pages_crawled", 0),    # articles saved
            "urls_processed": job.get("urls_processed", 0),  # URLs attempted
            "total_urls": job.get("total_urls"),              # None = BFS mode
        },
        logs=job.get("logs", []),
        error=job.get("error"),
    )


@router.post("/discover")
async def start_discovery(request: DiscoverRequest):
    """Start a background site discovery job"""
    job_id = str(uuid.uuid4())

    discovery_jobs[job_id] = {
        "status": "running",
        "url": str(request.url),
        "url_count": 0,
        "logs": [],
        "urls": [],
    }

    # Independent task — not tied to request lifecycle.
    asyncio.create_task(run_discovery_job(job_id, str(request.url)))

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Discovery started for {request.url}",
    }


@router.get("/discover/{job_id}", response_model=DiscoverStatusResponse)
async def get_discovery_status(job_id: str):
    """Get status of a discovery job"""
    if job_id not in discovery_jobs:
        raise HTTPException(status_code=404, detail="Discovery job not found")

    job = discovery_jobs[job_id]
    return DiscoverStatusResponse(
        job_id=job_id,
        status=job["status"],
        url_count=job.get("url_count", 0),
        logs=job.get("logs", []),
        urls=job.get("urls", []),
        error=job.get("error"),
    )


@router.get("/history")
async def list_crawl_history():
    """List all crawl jobs"""
    return {"jobs": list(crawl_jobs.values())}


@router.get("/domains")
async def list_domains():
    """List all domains that have stored URL files"""
    from app.crawler.domain_store import list_domains as _list_domains
    return {"domains": _list_domains()}


@router.get("/domains/{domain}/urls")
async def get_domain_urls(domain: str):
    """Get stored URLs for a domain"""
    from app.crawler.domain_store import load_urls, list_domains as _list_domains
    if domain not in _list_domains():
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")
    return {"domain": domain, "urls": load_urls(domain)}


async def run_discovery_job(job_id: str, url: str):
    """Background task that runs site discovery"""
    from app.crawler.discovery import SiteDiscovery
    from app.crawler.domain_store import normalize_domain, save_urls

    try:
        discovery = SiteDiscovery()

        def progress_callback(count: int, found_url: str):
            discovery_jobs[job_id]["url_count"] = count
            discovery_jobs[job_id]["logs"].append(f"[{count}] {found_url}")

        urls = await discovery.discover(url, on_progress=progress_callback)

        domain = normalize_domain(url)
        save_urls(domain, urls)

        discovery_jobs[job_id]["status"] = "completed"
        discovery_jobs[job_id]["url_count"] = len(urls)
        discovery_jobs[job_id]["urls"] = urls  # already sorted from discover()

    except asyncio.CancelledError:
        # Server is shutting down — preserve whatever was found so far.
        discovery_jobs[job_id]["status"] = "failed"
        discovery_jobs[job_id]["error"] = "Server shutdown during discovery."
        raise  # re-raise so asyncio can clean up properly
    except Exception as e:
        discovery_jobs[job_id]["status"] = "failed"
        discovery_jobs[job_id]["error"] = str(e)


async def run_crawl_job(
    job_id: str,
    url: str,
    max_pages: Optional[int],
    url_list: Optional[list[str]] = None,
):
    """Background task that runs the crawler.
    If url_list is provided, crawl exactly those URLs (list mode).
    Otherwise, BFS-crawl the site starting from url (discovery mode).
    """
    from app.database import AsyncSessionLocal
    from app.crawler.crawler import MedicalCrawler

    try:
        async with AsyncSessionLocal() as db:
            crawler = MedicalCrawler(db)
            total = len(url_list) if url_list else None

            if url_list:
                def list_progress(processed: int, saved: int, page_url: str, title: str, result: str):
                    crawl_jobs[job_id]["urls_processed"] = processed
                    crawl_jobs[job_id]["pages_crawled"] = saved
                    title_part = f" — {title.strip()[:60]}" if title.strip() else ""
                    if result == "ok":
                        prefix = f"[{processed}/{total}] ✓"
                    elif result == "fail":
                        prefix = f"[{processed}/{total}] ✗ FAIL"
                    else:
                        prefix = f"[{processed}/{total}] — SKIP"
                    crawl_jobs[job_id]["logs"].append(f"{prefix} {page_url}{title_part}")

                await crawler.crawl_url_list(url_list, on_progress=list_progress)
            else:
                def bfs_progress(count: int, page_url: str, title: str):
                    crawl_jobs[job_id]["pages_crawled"] = count
                    crawl_jobs[job_id]["urls_processed"] = count
                    title_part = f" — {title.strip()[:60]}" if title.strip() else ""
                    crawl_jobs[job_id]["logs"].append(f"[{count}] ✓ {page_url}{title_part}")

                await crawler.crawl_site(url, max_pages=max_pages, on_progress=bfs_progress)

            crawl_jobs[job_id]["status"] = "completed"

    except asyncio.CancelledError:
        crawl_jobs[job_id]["status"] = "failed"
        crawl_jobs[job_id]["error"] = "Server shutdown during crawl."
        raise
    except Exception as e:
        crawl_jobs[job_id]["status"] = "failed"
        crawl_jobs[job_id]["error"] = str(e)
