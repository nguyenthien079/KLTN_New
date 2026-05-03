import hashlib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.database import get_db
from app.models import Article, Sentence, Entity, LabelSubmission, LabelAnnotation, User, CrawlStatus
from app.auth import require_admin

router = APIRouter()


class ImportedFileIn(BaseModel):
    file_name: str
    relative_path: str
    clean_text: str


class ImportedArticleOut(BaseModel):
    article_id: int
    title: Optional[str]
    url: str
    clean_text: str


class ImportArticlesRequest(BaseModel):
    files: list[ImportedFileIn]


class ImportArticlesResponse(BaseModel):
    items: list[ImportedArticleOut]
    created: int
    updated: int


def _stem_from_path(path_or_name: str) -> str:
    return Path(path_or_name or "").stem


def _build_import_url(relative_path: str, file_name: str) -> str:
    safe_path = (relative_path or file_name or "").replace("\\", "/").strip("/")
    safe_path = safe_path.replace(" ", "_")
    return f"import://{safe_path}"


@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Get system-wide statistics"""
    article_count = await db.scalar(select(func.count(Article.id)))
    sentence_count = await db.scalar(select(func.count(Sentence.id)))

    entity_result = await db.execute(
        select(Entity.entity_type, func.count(Entity.id))
        .group_by(Entity.entity_type)
    )
    entity_by_type = {str(row[0]): row[1] for row in entity_result}

    return {
        "articles": article_count,
        "sentences": sentence_count,
        "entities": {
            "total": sum(entity_by_type.values()),
            "by_type": entity_by_type
        }
    }


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    submitted_count = await db.scalar(
        select(func.count(LabelSubmission.id)).where(LabelSubmission.status == "submitted")
    )
    reviewed_count = await db.scalar(
        select(func.count(LabelSubmission.id)).where(LabelSubmission.status.in_(["confirmed", "rejected"]))
    )
    total_annotations = await db.scalar(select(func.count(LabelAnnotation.id)))

    by_type_result = await db.execute(
        select(LabelAnnotation.entity_type, func.count(LabelAnnotation.id))
        .group_by(LabelAnnotation.entity_type)
    )
    annotations_by_type = {str(row[0]): row[1] for row in by_type_result}

    return {
        "submitted": submitted_count or 0,
        "reviewed": reviewed_count or 0,
        "total_annotations": total_annotations or 0,
        "annotations_by_type": annotations_by_type,
    }


@router.post("/articles/import", response_model=ImportArticlesResponse)
async def import_articles_from_files(
    request: ImportArticlesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not request.files:
        raise HTTPException(status_code=400, detail="Danh sách file nhập rỗng")

    items: list[ImportedArticleOut] = []
    created = 0
    updated = 0

    for file_item in request.files:
        title = _stem_from_path(file_item.relative_path or file_item.file_name) or _stem_from_path(file_item.file_name)
        import_url = _build_import_url(file_item.relative_path, file_item.file_name)
        clean_text = file_item.clean_text or ""
        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        source_domain = (Path(file_item.relative_path).parts[0] if Path(file_item.relative_path).parts else None) or None

        existing_result = await db.execute(select(Article).where(Article.url == import_url))
        article = existing_result.scalar_one_or_none()

        if article is None:
            article = Article(
                url=import_url,
                title=title,
                source_domain=source_domain,
                clean_text=clean_text,
                char_count=len(clean_text),
                content_hash=content_hash,
                status=CrawlStatus.PENDING,
            )
            db.add(article)
            await db.flush()
            created += 1
        else:
            article.title = title or article.title
            article.source_domain = source_domain or article.source_domain
            article.clean_text = clean_text
            article.char_count = len(clean_text)
            article.content_hash = content_hash
            article.status = article.status or CrawlStatus.PENDING
            updated += 1

        items.append(
            ImportedArticleOut(
                article_id=article.id,
                title=article.title,
                url=article.url,
                clean_text=article.clean_text or "",
            )
        )

    await db.commit()
    return ImportArticlesResponse(items=items, created=created, updated=updated)
