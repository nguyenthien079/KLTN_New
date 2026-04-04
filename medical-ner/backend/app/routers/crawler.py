import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()

# In-memory job tracking (production: use Redis/Celery)
crawl_jobs: dict = {}


class CrawlStartRequest(BaseModel):
    url: str
    max_pages: Optional[int] = 100


class CrawlStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: dict


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
        "max_pages": request.max_pages
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
            "max_pages": job.get("max_pages", 0)
        }
    )


@router.get("/history")
async def list_crawl_history():
    """List all crawl jobs"""
    return {"jobs": list(crawl_jobs.values())}


async def run_crawl_job(job_id: str, url: str, max_pages: int):
    """Background task that runs the crawler"""
    from app.database import AsyncSessionLocal
    from app.crawler.crawler import MedicalCrawler

    try:
        async with AsyncSessionLocal() as db:
            crawler = MedicalCrawler(db)
            articles = await crawler.crawl_site(url, max_pages=max_pages)

            crawl_jobs[job_id]["status"] = "completed"
            crawl_jobs[job_id]["pages_crawled"] = len(articles)

    except Exception as e:
        crawl_jobs[job_id]["status"] = "failed"
        crawl_jobs[job_id]["error"] = str(e)
