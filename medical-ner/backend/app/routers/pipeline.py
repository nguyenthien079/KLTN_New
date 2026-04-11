import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_admin
from app.models.user import User

router = APIRouter()

pipeline_jobs: dict = {}
filter_jobs: dict = {}


class ProcessRequest(BaseModel):
    article_id: Optional[int] = None  # None = process all


@router.post("/process")
async def process_articles(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Start a pipeline processing job"""
    job_id = str(uuid.uuid4())

    pipeline_jobs[job_id] = {
        "status": "running",
        "article_id": request.article_id,
        "articles_processed": 0,
        "total_sentences": 0,
        "logs": []
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
            pipeline_jobs[job_id]["logs"].append("Đang khởi động pipeline...")

            if article_id is not None:
                stats = await pipeline.process_article(article_id)
                pipeline_jobs[job_id]["articles_processed"] = 1
                pipeline_jobs[job_id]["total_sentences"] = stats["sentences_after_dedup"]
                pipeline_jobs[job_id]["logs"].append(f"Hoàn tất: 1 bài, {stats['sentences_after_dedup']} câu")
            else:
                stats = await pipeline.process_all_articles()
                pipeline_jobs[job_id]["articles_processed"] = stats["articles_processed"]
                pipeline_jobs[job_id]["total_sentences"] = stats["total_sentences"]
                pipeline_jobs[job_id]["logs"].append(f"Hoàn tất: {stats['articles_processed']} bài, {stats['total_sentences']} câu")

            pipeline_jobs[job_id]["status"] = "completed"

    except Exception as e:
        pipeline_jobs[job_id]["status"] = "failed"
        pipeline_jobs[job_id]["error"] = str(e)
        pipeline_jobs[job_id]["logs"].append(f"Lỗi: {str(e)}")


@router.post("/filter")
async def start_filter(
    background_tasks: BackgroundTasks,
    _: User = Depends(require_admin),
):
    """Run filter_quality as background job"""
    job_id = str(uuid.uuid4())
    filter_jobs[job_id] = {"status": "running", "logs": [], "result": {}}
    background_tasks.add_task(run_filter_job, job_id)
    return {"job_id": job_id, "status": "started"}


@router.get("/filter/{job_id}")
async def get_filter_status(job_id: str):
    from fastapi import HTTPException
    if job_id not in filter_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return filter_jobs[job_id]


async def run_filter_job(job_id: str):
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import Article

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Article))
            articles = result.scalars().all()
            total = len(articles)
            filter_jobs[job_id]["logs"].append(f"Tổng bài: {total}")

            removed = 0
            for article in articles:
                reason = None
                if not article.clean_text:
                    reason = "no text"
                elif len(article.clean_text) < 200:
                    reason = f"quá ngắn ({len(article.clean_text)} ký tự)"
                elif len(article.clean_text) > 50000:
                    reason = f"quá dài ({len(article.clean_text)} ký tự)"
                elif article.clean_text.count(' ') < 20:
                    reason = "quá ít từ"

                if reason:
                    await db.delete(article)
                    removed += 1
                    filter_jobs[job_id]["logs"].append(
                        f"[xóa] {(article.title or article.url or '')[:60]} — {reason}"
                    )

            await db.commit()
            remaining = total - removed
            filter_jobs[job_id]["logs"].append(
                f"Hoàn tất: xóa {removed}, còn lại {remaining} bài"
            )
            filter_jobs[job_id]["status"] = "completed"
            filter_jobs[job_id]["result"] = {"removed": removed, "remaining": remaining}

    except Exception as e:
        filter_jobs[job_id]["status"] = "failed"
        filter_jobs[job_id]["logs"].append(f"Lỗi: {str(e)}")
