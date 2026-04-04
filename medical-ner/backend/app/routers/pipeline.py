import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()

pipeline_jobs: dict = {}


class ProcessRequest(BaseModel):
    article_id: Optional[int] = None  # None = process all


@router.post("/process")
async def process_articles(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a pipeline processing job"""
    job_id = str(uuid.uuid4())

    pipeline_jobs[job_id] = {
        "status": "running",
        "article_id": request.article_id,
        "articles_processed": 0,
        "total_sentences": 0
    }

    background_tasks.add_task(run_pipeline_job, job_id, request.article_id)

    return {
        "job_id": job_id,
        "status": "started",
        "message": "Pipeline job started"
    }


@router.get("/status/{job_id}")
async def get_pipeline_status(job_id: str):
    from fastapi import HTTPException
    if job_id not in pipeline_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return pipeline_jobs[job_id]


async def run_pipeline_job(job_id: str, article_id: Optional[int]):
    from app.database import AsyncSessionLocal
    from app.pipeline.pipeline import MedicalTextPipeline

    try:
        async with AsyncSessionLocal() as db:
            pipeline = MedicalTextPipeline(db)

            if article_id:
                stats = await pipeline.process_article(article_id)
                pipeline_jobs[job_id]["articles_processed"] = 1
                pipeline_jobs[job_id]["total_sentences"] = stats["sentences_after_dedup"]
            else:
                stats = await pipeline.process_all_articles()
                pipeline_jobs[job_id]["articles_processed"] = stats["articles_processed"]
                pipeline_jobs[job_id]["total_sentences"] = stats["total_sentences"]

            pipeline_jobs[job_id]["status"] = "completed"

    except Exception as e:
        pipeline_jobs[job_id]["status"] = "failed"
        pipeline_jobs[job_id]["error"] = str(e)
