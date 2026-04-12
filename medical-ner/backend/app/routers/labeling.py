# backend/app/routers/labeling.py
from fastapi import APIRouter, Depends, HTTPException
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
from app.auth import get_current_user, require_expert_or_admin

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


# ── Endpoints ─────────────────────────────────────────────

@router.get("/articles", response_model=list[ArticleListItem])
async def list_articles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all articles available for labeling with status per current user."""
    articles_result = await db.execute(
        select(Article).order_by(Article.id).limit(200)
    )
    articles = articles_result.scalars().all()

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

    # assignments for current user
    assigned_result = await db.execute(
        select(LabelAssignment.article_id)
        .where(LabelAssignment.labeler_id == user.id)
    )
    assigned_ids = {row[0] for row in assigned_result}

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
    if user.role == "labeler":
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
        sub = LabelSubmission(article_id=article_id, labeler_id=user.id)
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
    user: User = Depends(require_expert_or_admin),
):
    """Admin or expert assigns an article to a labeler."""
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


@router.patch("/assignments/{assignment_id}/blind-mode")
async def toggle_blind_mode(
    assignment_id: str,
    body: BlindModeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_expert_or_admin),
):
    """Toggle blind mode for a specific assignment."""
    a = await db.get(LabelAssignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment không tồn tại")
    a.blind_mode = body.blind_mode
    await db.commit()
    return {"assignment_id": assignment_id, "blind_mode": body.blind_mode}
