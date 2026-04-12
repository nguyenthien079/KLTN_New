"""Run once to create labeling tables. python scripts/migrate_labeling_tables.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
from app.models import Article, Sentence, Entity, KnowledgeMap, Correction, User  # noqa
from app.models.role_request import RoleRequest  # noqa
from app.models.label_assignment import LabelAssignment  # noqa  (created in Task 3)
from app.models.label_submission import LabelSubmission  # noqa
from app.models.label_annotation import LabelAnnotation  # noqa


async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("All labeling tables created.")


if __name__ == "__main__":
    asyncio.run(migrate())
