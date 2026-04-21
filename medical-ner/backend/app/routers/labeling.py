# backend/app/routers/labeling.py
import csv
import io
import json as json_lib
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.article import Article
from app.models.label_assignment import LabelAssignment
from app.models.label_submission import LabelSubmission
from app.models.label_annotation import LabelAnnotation
from app.models.entity import Entity, EntityType
from app.auth import get_current_user

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_DICT_DIR = _DATA_DIR / "dicts"
_TRAINING_QUEUE_FILE = _DATA_DIR / "training_queue.jsonl"

_ENTITY_TYPE_TO_DICT: dict[str, str] = {
    "DISEASE": "diseases.txt",
    "DRUG": "drugs.txt",
    "SYMPTOM": "symptoms.txt",
    "TREATMENT": "treatments.txt",
    "BODY_PART": "body_parts.txt",
    "TEST": "tests.txt",
}

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────

class AnnotationIn(BaseModel):
    entity_type: str
    start_offset: int
    end_offset: int
    surface_text: Optional[str] = None
    comment: Optional[str] = None


class SubmissionSaveRequest(BaseModel):
    annotations: list[AnnotationIn]
    submit: bool = False  # True = mark as submitted


class AssignRequest(BaseModel):
    article_id: int
    labeler_id: str
    blind_mode: bool = False


class BulkAssignRequest(BaseModel):
    article_ids: list[int]
    labeler_ids: list[str]
    blind_mode: bool = False
    initial_annotations: dict[str, list[AnnotationIn]] = {}


class BlindModeRequest(BaseModel):
    blind_mode: bool


class ArticleDetail(BaseModel):
    article_id: int
    title: Optional[str]
    url: str
    clean_text: str


class ArticleListItem(BaseModel):
    article_id: int
    title: Optional[str]
    url: str
    submission_count: int
    my_status: Optional[str]  # draft | submitted | None
    assigned_to_me: bool


class AnnotationOut(BaseModel):
    id: str
    entity_type: str
    start_offset: int
    end_offset: int
    surface_text: Optional[str]
    comment: Optional[str]


class SubmissionOut(BaseModel):
    submission_id: str
    labeler_id: str
    labeler_name: Optional[str]
    status: str
    annotations: list[AnnotationOut]


class ReviewQueueItem(BaseModel):
    id: str
    article_id: int
    article_title: Optional[str]
    original_text: str
    original_entities: list
    corrected_entities: list
    status: str
    labeler_id: str


class NotificationItem(BaseModel):
    article_id: int
    article_title: Optional[str]
    created_at: Optional[str]
    message: str


# ── Endpoints ─────────────────────────────────────────────

@router.get("/articles", response_model=list[ArticleListItem])
async def list_articles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all articles available for labeling with status per current user."""
    # Experts only see files explicitly assigned by admin.
    if user.role == "chuyen_gia":
        assigned_result = await db.execute(
            select(LabelAssignment.article_id)
            .where(LabelAssignment.labeler_id == user.id)
            .where(
                LabelAssignment.assigned_by.in_(
                    select(User.id).where(User.role == "admin")
                )
            )
        )
        assigned_ids = {row[0] for row in assigned_result}
        if not assigned_ids:
            return []

        articles_result = await db.execute(
            select(Article)
            .where(Article.id.in_(assigned_ids))
            .order_by(Article.id)
            .limit(200)
        )
        articles = articles_result.scalars().all()
    else:
        articles_result = await db.execute(
            select(Article).order_by(Article.id).limit(200)
        )
        articles = articles_result.scalars().all()

        assigned_result = await db.execute(
            select(LabelAssignment.article_id)
            .where(LabelAssignment.labeler_id == user.id)
        )
        assigned_ids = {row[0] for row in assigned_result}

    # submission counts per article
    counts_result = await db.execute(
        select(LabelSubmission.article_id, func.count(LabelSubmission.id))
        .group_by(LabelSubmission.article_id)
    )
    counts = {row[0]: row[1] for row in counts_result}

    # current user's submissions
    my_subs_result = await db.execute(
        select(LabelSubmission.article_id, LabelSubmission.status)
        .where(LabelSubmission.labeler_id == user.id)
    )
    my_subs = {row[0]: row[1] for row in my_subs_result}

    return [
        ArticleListItem(
            article_id=a.id,
            title=a.title,
            url=a.url,
            submission_count=counts.get(a.id, 0),
            my_status=my_subs.get(a.id),
            assigned_to_me=a.id in assigned_ids,
        )
        for a in articles
    ]


@router.get("/articles/{article_id}", response_model=ArticleDetail)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    return ArticleDetail(
        article_id=article.id,
        title=article.title,
        url=article.url,
        clean_text=article.clean_text or "",
    )


@router.get("/articles/{article_id}/submissions", response_model=list[SubmissionOut])
async def get_article_submissions(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all submissions for an article.
    Labelers: see own + others unless blind_mode is on for their assignment.
    Experts/admins: always see all.
    """
    # Check blind mode for this user on this article
    blind = False
    if user.role == "chuyen_gia":
        assign = await db.execute(
            select(LabelAssignment)
            .where(LabelAssignment.article_id == article_id)
            .where(LabelAssignment.labeler_id == user.id)
        )
        a = assign.scalar_one_or_none()
        blind = a.blind_mode if a else False

    subs_result = await db.execute(
        select(LabelSubmission)
        .where(LabelSubmission.article_id == article_id)
        .options(selectinload(LabelSubmission.annotations))
    )
    subs = subs_result.scalars().all()

    # batch-load user display names
    labeler_ids = {s.labeler_id for s in subs}
    users_result = await db.execute(select(User).where(User.id.in_(labeler_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    out = []
    for sub in subs:
        if blind and sub.labeler_id != user.id:
            continue

        labeler = users_map.get(sub.labeler_id)
        out.append(SubmissionOut(
            submission_id=sub.id,
            labeler_id=sub.labeler_id,
            labeler_name=(labeler.display_name or labeler.username) if labeler else sub.labeler_id[:8],
            status=sub.status,
            annotations=[
                AnnotationOut(
                    id=ann.id,
                    entity_type=ann.entity_type,
                    start_offset=ann.start_offset,
                    end_offset=ann.end_offset,
                    surface_text=ann.surface_text,
                    comment=ann.comment,
                )
                for ann in sub.annotations
            ],
        ))
    return out


@router.post("/articles/{article_id}/save")
async def save_submission(
    article_id: int,
    request: SubmissionSaveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save (or submit) current user's annotation for an article.
    Replaces all existing annotations for this user+article.
    """
    # Get or create submission
    sub_result = await db.execute(
        select(LabelSubmission)
        .where(LabelSubmission.article_id == article_id)
        .where(LabelSubmission.labeler_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()

    if sub is None:
        # Snapshot model predictions once at session start
        predictions = []
        article = await db.get(Article, article_id)
        if article and article.clean_text and article.clean_text.strip():
            try:
                from app.routers.ner import get_ner_pipeline
                import asyncio
                pipeline = get_ner_pipeline()
                loop = asyncio.get_running_loop()
                entities = await loop.run_in_executor(None, pipeline.extract, article.clean_text)
                predictions = [
                    {"text": e.text, "type": e.entity_type, "start": e.start, "end": e.end, "source": e.source}
                    for e in entities
                ]
            except Exception:
                pass
        sub = LabelSubmission(article_id=article_id, labeler_id=user.id, model_predictions=predictions)
        db.add(sub)
        await db.flush()
    elif sub.status == "submitted" and not request.submit:
        # Allow re-opening draft after submit
        sub.status = "draft"

    await db.execute(
        sa_delete(LabelAnnotation).where(LabelAnnotation.submission_id == sub.id)
    )

    for ann_in in request.annotations:
        ann = LabelAnnotation(
            submission_id=sub.id,
            entity_type=ann_in.entity_type,
            start_offset=ann_in.start_offset,
            end_offset=ann_in.end_offset,
            surface_text=ann_in.surface_text,
            comment=ann_in.comment,
        )
        db.add(ann)

    if request.submit:
        sub.status = "submitted"

    await db.commit()
    return {"submission_id": sub.id, "status": sub.status}


@router.post("/assign")
async def assign_article(
    request: AssignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Admin assigns one or more articles to experts."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền bàn giao")

    existing = await db.execute(
        select(LabelAssignment)
        .where(LabelAssignment.article_id == request.article_id)
        .where(LabelAssignment.labeler_id == request.labeler_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Đã được assign trước đó")

    labeler_result = await db.execute(
        select(User).where(User.id == request.labeler_id)
    )
    if not labeler_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Labeler không tồn tại")

    assignment = LabelAssignment(
        article_id=request.article_id,
        labeler_id=request.labeler_id,
        assigned_by=user.id,
        blind_mode=request.blind_mode,
    )
    db.add(assignment)
    await db.commit()
    return {"status": "assigned"}


@router.post("/assign/bulk")
async def assign_articles_bulk(
    request: BulkAssignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Admin assigns multiple articles to multiple experts in one request."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền bàn giao")

    article_ids = sorted({aid for aid in request.article_ids if aid is not None})
    labeler_ids = sorted({lid for lid in request.labeler_ids if lid})

    if not article_ids:
        raise HTTPException(status_code=400, detail="Danh sách file/text rỗng")
    if not labeler_ids:
        raise HTTPException(status_code=400, detail="Danh sách chuyên gia rỗng")

    # Validate articles exist
    articles_result = await db.execute(select(Article.id).where(Article.id.in_(article_ids)))
    existing_article_ids = {row[0] for row in articles_result}
    missing_article_ids = [aid for aid in article_ids if aid not in existing_article_ids]
    if missing_article_ids:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy article_id: {missing_article_ids}")

    # Validate experts
    users_result = await db.execute(
        select(User.id).where(User.id.in_(labeler_ids)).where(User.role == "chuyen_gia")
    )
    expert_ids = {row[0] for row in users_result}
    missing_experts = [uid for uid in labeler_ids if uid not in expert_ids]
    if missing_experts:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy chuyên gia hợp lệ: {missing_experts}")

    existing_pairs_result = await db.execute(
        select(LabelAssignment.article_id, LabelAssignment.labeler_id)
        .where(LabelAssignment.article_id.in_(article_ids))
        .where(LabelAssignment.labeler_id.in_(labeler_ids))
    )
    existing_pairs = {(row[0], row[1]) for row in existing_pairs_result}

    # Normalize imported annotations by article_id for later draft seeding.
    initial_annotations_by_article: dict[int, list[AnnotationIn]] = {}
    for article_id_key, annotations in (request.initial_annotations or {}).items():
        try:
            normalized_article_id = int(article_id_key)
        except (TypeError, ValueError):
            continue
        if normalized_article_id in article_ids:
            initial_annotations_by_article[normalized_article_id] = annotations or []

    created = 0
    skipped = 0
    for article_id in article_ids:
        for labeler_id in labeler_ids:
            if (article_id, labeler_id) in existing_pairs:
                skipped += 1
                continue
            db.add(
                LabelAssignment(
                    article_id=article_id,
                    labeler_id=labeler_id,
                    assigned_by=user.id,
                    blind_mode=request.blind_mode,
                )
            )
            created += 1

            if initial_annotations_by_article.get(article_id):
                sub_result = await db.execute(
                    select(LabelSubmission)
                    .where(LabelSubmission.article_id == article_id)
                    .where(LabelSubmission.labeler_id == labeler_id)
                )
                submission = sub_result.scalar_one_or_none()
                if submission is None:
                    submission = LabelSubmission(
                        article_id=article_id,
                        labeler_id=labeler_id,
                        status="draft",
                    )
                    db.add(submission)
                    await db.flush()

                    for ann_in in initial_annotations_by_article[article_id]:
                        db.add(
                            LabelAnnotation(
                                submission_id=submission.id,
                                entity_type=ann_in.entity_type,
                                start_offset=ann_in.start_offset,
                                end_offset=ann_in.end_offset,
                                surface_text=ann_in.surface_text,
                                comment=ann_in.comment,
                            )
                        )

    await db.commit()
    return {
        "status": "assigned",
        "created": created,
        "skipped": skipped,
        "article_count": len(article_ids),
        "expert_count": len(labeler_ids),
    }


@router.get("/notifications", response_model=list[NotificationItem])
async def get_notifications(
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recent assignment notifications for experts."""
    if user.role != "chuyen_gia":
        return []

    result = await db.execute(
        select(LabelAssignment, Article.title)
        .join(Article, Article.id == LabelAssignment.article_id)
        .where(LabelAssignment.labeler_id == user.id)
        .where(
            LabelAssignment.assigned_by.in_(
                select(User.id).where(User.role == "admin")
            )
        )
        .order_by(LabelAssignment.created_at.desc())
        .limit(limit)
    )

    notifications = []
    for assignment, article_title in result.all():
        title = article_title or f"Bài {assignment.article_id}"
        created_at = assignment.created_at.isoformat() if assignment.created_at else None
        notifications.append(
            NotificationItem(
                article_id=assignment.article_id,
                article_title=article_title,
                created_at=created_at,
                message=f"Admin đã bàn giao: {title}",
            )
        )
    return notifications


@router.get("/articles/{article_id}/suggest")
async def suggest_annotations(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Auto-suggest annotations using full ensemble NER (PhoBERT + dictionary + rules)."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

    text = article.clean_text or ""
    if not text.strip():
        return {"article_id": article_id, "suggestions": []}

    from app.routers.ner import get_ner_pipeline
    import asyncio
    pipeline = get_ner_pipeline()
    loop = asyncio.get_event_loop()
    entities = await loop.run_in_executor(None, pipeline.extract, text)

    return {
        "article_id": article_id,
        "suggestions": [
            {
                "entity_type": e.entity_type,
                "start_offset": e.start,
                "end_offset": e.end,
                "surface_text": e.text,
                "source": e.source,
            }
            for e in entities
        ],
    }


@router.get("/articles/{article_id}/export")
async def export_article_annotations(
    article_id: int,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export all submitted annotations for an article as JSON or CSV.
    Only submitted annotations are included. Requires expert or admin role.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

    subs_result = await db.execute(
        select(LabelSubmission)
        .where(LabelSubmission.article_id == article_id)
        .where(LabelSubmission.status.in_(["submitted", "confirmed"]))
        .options(selectinload(LabelSubmission.annotations))
    )
    subs = subs_result.scalars().all()

    # batch-load labeler names
    labeler_ids = {s.labeler_id for s in subs}
    users_result = await db.execute(select(User).where(User.id.in_(labeler_ids)))
    users_map = {u.id: (u.display_name or u.username) for u in users_result.scalars().all()}

    clean_text = article.clean_text or ""

    if format == "json":
        data = {
            "article_id": article_id,
            "title": article.title,
            "url": article.url,
            "full_text": clean_text,
            "submissions": [
                {
                    "labeler": users_map.get(s.labeler_id, s.labeler_id[:8]),
                    "status": s.status,
                    "annotations": [
                        {
                            "entity_type": ann.entity_type,
                            "start_offset": ann.start_offset,
                            "end_offset": ann.end_offset,
                            "surface_text": ann.surface_text,
                            "comment": ann.comment,
                        }
                        for ann in sorted(s.annotations, key=lambda a: a.start_offset)
                    ],
                }
                for s in subs
            ],
        }
        filename = f"article_{article_id}_annotations.json"
        return Response(
            content=json_lib.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["article_id", "title", "labeler", "entity_type",
                     "start_offset", "end_offset", "surface_text", "comment"])
    for s in subs:
        labeler_name = users_map.get(s.labeler_id, s.labeler_id[:8])
        for ann in sorted(s.annotations, key=lambda a: a.start_offset):
            writer.writerow([
                article_id,
                article.title or "",
                labeler_name,
                ann.entity_type,
                ann.start_offset,
                ann.end_offset,
                ann.surface_text or "",
                ann.comment or "",
            ])

    filename = f"article_{article_id}_annotations.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/assignments/{assignment_id}/blind-mode")
async def toggle_blind_mode(
    assignment_id: str,
    body: BlindModeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Toggle blind mode for a specific assignment."""
    a = await db.get(LabelAssignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment không tồn tại")
    a.blind_mode = body.blind_mode
    await db.commit()
    return {"assignment_id": assignment_id, "blind_mode": body.blind_mode}


@router.get("/review/queue", response_model=list[ReviewQueueItem])
async def get_label_review_queue(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Expert/Admin: list submitted and reviewed label submissions."""
    result = await db.execute(
        select(LabelSubmission)
        .where(LabelSubmission.status.in_(["submitted", "confirmed", "rejected"]))
        .options(selectinload(LabelSubmission.annotations))
        .order_by(LabelSubmission.updated_at.desc())
    )
    submissions = result.scalars().all()

    article_ids = {s.article_id for s in submissions}
    labeler_ids = {s.labeler_id for s in submissions}

    articles_map = {}
    if article_ids:
        articles_result = await db.execute(select(Article).where(Article.id.in_(article_ids)))
        articles_map = {a.id: a for a in articles_result.scalars().all()}

    users_map = {}
    if labeler_ids:
        users_result = await db.execute(select(User).where(User.id.in_(labeler_ids)))
        users_map = {u.id: u for u in users_result.scalars().all()}

    items = []
    for sub in submissions:
        article = articles_map.get(sub.article_id)
        labeler = users_map.get(sub.labeler_id)
        items.append(ReviewQueueItem(
            id=sub.id,
            article_id=sub.article_id,
            article_title=article.title if article else None,
            original_text=article.clean_text if article and article.clean_text else "",
            original_entities=sub.model_predictions or [],
            corrected_entities=[
                {
                    "text": ann.surface_text or "",
                    "type": ann.entity_type,
                    "start": ann.start_offset,
                    "end": ann.end_offset,
                    "comment": ann.comment,
                }
                for ann in sorted(sub.annotations, key=lambda a: a.start_offset)
            ],
            status="pending_review" if sub.status == "submitted" else sub.status,
            labeler_id=(labeler.display_name or labeler.username) if labeler else sub.labeler_id,
        ))

    return items


@router.patch("/review/{submission_id}/confirm")
async def confirm_label_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LabelSubmission)
        .where(LabelSubmission.id == submission_id)
        .options(selectinload(LabelSubmission.annotations))
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Không tìm thấy submission")
    sub.status = "confirmed"

    annotations = sub.annotations or []
    if annotations:
        await _expand_dicts(annotations)
        await _append_training_queue(sub, annotations)
        await _upsert_entities(db, sub.article_id, annotations)

    await db.commit()
    return {"id": submission_id, "status": "confirmed"}


async def _expand_dicts(annotations: list[LabelAnnotation]) -> None:
    """A2: append new surface_text to the relevant dictionary file."""
    for ann in annotations:
        if not ann.surface_text:
            continue
        dict_file = _DICT_DIR / _ENTITY_TYPE_TO_DICT.get(ann.entity_type.upper(), "")
        if not dict_file.name or not dict_file.exists():
            continue
        term = ann.surface_text.strip().lower()
        existing = {line.strip().lower() for line in dict_file.read_text(encoding="utf-8").splitlines() if line.strip()}
        if term not in existing:
            with dict_file.open("a", encoding="utf-8") as f:
                f.write(f"\n{term}")


async def _append_training_queue(sub: LabelSubmission, annotations: list[LabelAnnotation]) -> None:
    """A2: write confirmed annotations to training queue for future fine-tuning."""
    entry = {
        "submission_id": sub.id,
        "article_id": sub.article_id,
        "labeler_id": sub.labeler_id,
        "annotations": [
            {
                "entity_type": a.entity_type,
                "start_offset": a.start_offset,
                "end_offset": a.end_offset,
                "surface_text": a.surface_text,
            }
            for a in annotations
        ],
    }
    _TRAINING_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _TRAINING_QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(json_lib.dumps(entry, ensure_ascii=False) + "\n")


async def _upsert_entities(db: AsyncSession, article_id: int, annotations: list[LabelAnnotation]) -> None:
    """A5: upsert confirmed human annotations into the Entity table."""
    for ann in annotations:
        if not ann.surface_text:
            continue
        raw_type = ann.entity_type.upper()
        try:
            etype = EntityType(raw_type)
        except ValueError:
            continue

        normalized = ann.surface_text.strip().lower()
        result = await db.execute(
            select(Entity).where(
                Entity.normalized_text == normalized,
                Entity.entity_type == etype,
            )
        )
        entity = result.scalar_one_or_none()
        if entity:
            entity.frequency = (entity.frequency or 1) + 1
        else:
            db.add(Entity(
                text=ann.surface_text.strip(),
                normalized_text=normalized,
                entity_type=etype,
                frequency=1,
                avg_confidence=1.0,
            ))


@router.patch("/review/{submission_id}/reject")
async def reject_label_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(LabelSubmission).where(LabelSubmission.id == submission_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Không tìm thấy submission")
    sub.status = "rejected"
    await db.commit()
    return {"id": submission_id, "status": "rejected"}
