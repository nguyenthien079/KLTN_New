from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Article, Sentence, Entity, LabelSubmission, LabelAnnotation, User
from app.auth import require_admin

router = APIRouter()


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
