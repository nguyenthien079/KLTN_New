from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Article, Sentence, Entity

router = APIRouter()


@router.get("/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db)):
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
