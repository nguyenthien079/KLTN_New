import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()

# In-memory job tracking (production: use Redis/Celery)
crawl_jobs: dict = {}
discovery_jobs: dict = {}


class DiscoverRequest(BaseModel):
    url: str


class DiscoverStatusResponse(BaseModel):
    job_id: str
    status: str
    url_count: int
    logs: list[str] = []
    urls: list[str] = []


class CrawlStartRequest(BaseModel):
    url: str
    max_pages: Optional[int] = None


class CrawlStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: dict
    logs: list[str] = []


@router.post("/start")
async def start_crawl(
    request: CrawlStartRequest,
    background_tasks: BackgroundTasks,
):
    """Start a background crawl job"""
    job_id = str(uuid.uuid4())

    crawl_jobs[job_id] = {
        "status": "running",
        "url": request.url,
        "pages_crawled": 0,
        "logs": []
    }

    background_tasks.add_task(
        run_crawl_job,
        job_id,
        request.url,
        request.max_pages
    )

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Crawl job started for {request.url}"
    }


@router.get("/status/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: str):
    """Get status of a crawl job"""
    from fastapi import HTTPException
    if job_id not in crawl_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = crawl_jobs[job_id]
    return CrawlStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress={
            "pages_crawled": job.get("pages_crawled", 0),
        },
        logs=job.get("logs", [])
    )


@router.post("/discover")
async def start_discovery(
    request: DiscoverRequest,
    background_tasks: BackgroundTasks,
):
    """Start a background site discovery job"""
    job_id = str(uuid.uuid4())

    discovery_jobs[job_id] = {
        "status": "running",
        "url": request.url,
        "url_count": 0,
        "logs": [],
        "urls": [],
    }

    background_tasks.add_task(run_discovery_job, job_id, request.url)

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Discovery started for {request.url}",
    }


@router.get("/discover/{job_id}", response_model=DiscoverStatusResponse)
async def get_discovery_status(job_id: str):
    """Get status of a discovery job"""
    from fastapi import HTTPException
    if job_id not in discovery_jobs:
        raise HTTPException(status_code=404, detail="Discovery job not found")

    job = discovery_jobs[job_id]
    return DiscoverStatusResponse(
        job_id=job_id,
        status=job["status"],
        url_count=job.get("url_count", 0),
        logs=job.get("logs", []),
        urls=job.get("urls", []),
    )


@router.get("/history")
async def list_crawl_history():
    """List all crawl jobs"""
    return {"jobs": list(crawl_jobs.values())}


async def run_discovery_job(job_id: str, url: str):
    """Background task that runs site discovery"""
    from app.crawler.discovery import SiteDiscovery

    try:
        discovery = SiteDiscovery()

        def progress_callback(count: int, found_url: str):
            discovery_jobs[job_id]["url_count"] = count
            discovery_jobs[job_id]["logs"].append(f"[{count}] {found_url}")
            discovery_jobs[job_id]["urls"].append(found_url)

        urls = await discovery.discover(url, on_progress=progress_callback)

        discovery_jobs[job_id]["status"] = "completed"
        discovery_jobs[job_id]["url_count"] = len(urls)

    except ValueError as e:
        discovery_jobs[job_id]["status"] = "failed"
        discovery_jobs[job_id]["error"] = str(e)
    except Exception as e:
        discovery_jobs[job_id]["status"] = "failed"
        discovery_jobs[job_id]["error"] = str(e)


async def run_crawl_job(job_id: str, url: str, max_pages: Optional[int]):
    """Background task that runs the crawler"""
    from app.database import AsyncSessionLocal
    from app.crawler.crawler import MedicalCrawler

    try:
        async with AsyncSessionLocal() as db:
            crawler = MedicalCrawler(db)

            def progress_callback(count: int, page_url: str, title: str):
                crawl_jobs[job_id]["pages_crawled"] = count
                label = title.strip()[:70] if title.strip() else page_url
                crawl_jobs[job_id]["logs"].append(
                    f"[{count}] {label}"
                )

            articles = await crawler.crawl_site(
                url, max_pages=max_pages, on_progress=progress_callback
            )

            crawl_jobs[job_id]["status"] = "completed"

    except Exception as e:
        crawl_jobs[job_id]["status"] = "failed"
        crawl_jobs[job_id]["error"] = str(e)
