# Labeling System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a collaborative annotation system where labelers annotate Vietnamese medical text, experts review and resolve conflicts, with role-based access (labeler / chuyên gia / admin).

**Architecture:** New DB tables (role_requests, label_assignments, label_submissions, label_annotations) + new backend routers (/api/labeling, /api/role-requests) + new frontend tab "Labeling" with inline annotation UI. Expert review is integrated into the existing "Duyệt nhãn" tab. Role `chuyen_gia` added alongside existing `admin`/`labeler`.

**Tech Stack:** FastAPI async, SQLAlchemy, PostgreSQL, React, CSS variables design system (existing)

---

## Context from design session

### Permission matrix (UPDATED)

| Tab | Labeler | Chuyên gia | Admin |
|---|---|---|---|
| Phân tích NER | ✓ | ✓ | ✓ |
| Thu thập dữ liệu | ✓ | ✓ | ✓ |
| Pipeline | ✗ | ✓ | ✓ |
| Labeling | ✓ | ✓ | ✓ |
| Duyệt nhãn | ✗ | ✓ | ✓ |
| Người dùng | ✗ | ✗ | ✓ |

### Annotation format (`.pipe` inspired)
Each annotation: `entity_type | start_offset | end_offset` (character positions on `article.clean_text`).
Entity types reuse the existing NER types from `frontend/src/config/entityConfig.js`.

### Blind mode
Default OFF — labelers can see each other's annotations as reference.
Admin/chuyên gia can toggle blind mode per article via `label_assignments.blind_mode`.

### Labeling workflow
1. Labeler picks article from list (or gets assigned)
2. Annotates text (mouse select → popup → entity type + optional comment)
3. Saves draft, can re-edit any time before Submit
4. Submits → `label_submissions.status = "submitted"`
5. Chuyên gia opens Duyệt nhãn, picks article, sees all submissions overlaid
6. Per annotation: Accept / Reject + optional note
7. "Hoàn thành review" is PENDING (user will decide later what to export/store)

### "Xin Cấp Quyền lên Chuyên gia"
- Labeler sees button in nav (next to username)
- Creates `role_requests` record with status=`pending`
- Admin sees pending requests in Users tab, approves → user.role = `chuyen_gia`

---

## Task 1: Add `chuyen_gia` role to backend

**Files:**
- Modify: `backend/app/auth.py`
- Modify: `backend/app/routers/users.py`

**Step 1: Update `require_admin` and add `require_expert_or_admin`**

In `backend/app/auth.py`, add after `require_admin`:

```python
def require_expert_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "chuyen_gia"):
        raise HTTPException(status_code=403, detail="Yêu cầu quyền chuyên gia trở lên")
    return user
```

**Step 2: Update `create_user` validation in users.py**

Change:
```python
if request.role not in ("admin", "labeler"):
    raise HTTPException(status_code=400, detail="Role phải là admin hoặc labeler")
```
To:
```python
if request.role not in ("admin", "labeler", "chuyen_gia"):
    raise HTTPException(status_code=400, detail="Role phải là admin, chuyen_gia hoặc labeler")
```

**Step 3: Update UsersPage.jsx select options**

In `frontend/src/components/UsersPage.jsx`, add option:
```jsx
<option value="chuyen_gia">Chuyên gia</option>
```

Update `ROLE_LABEL`:
```js
const ROLE_LABEL = { admin: 'Admin', chuyen_gia: 'Chuyên gia', labeler: 'Labeler' };
```

Add badge CSS in `UsersPage.css`:
```css
.users-role-badge--chuyen_gia { background: #fef3c7; color: #92400e; }
```

**Step 4: Update App.jsx tab visibility**

Current tabs array only checks `user.role === 'admin'`. Update to:

```jsx
const canSeePipeline = user.role === 'admin' || user.role === 'chuyen_gia';
const canSeeReview = user.role === 'admin' || user.role === 'chuyen_gia';
const canSeeUsers = user.role === 'admin';

const tabs = [
  { id: 'ner', label: 'Phân tích NER' },
  { id: 'crawl', label: 'Thu thập dữ liệu' },
  ...(canSeePipeline ? [{ id: 'pipeline', label: 'Pipeline' }] : []),
  { id: 'labeling', label: 'Labeling' },
  ...(canSeeReview ? [{ id: 'review', label: 'Duyệt nhãn' }] : []),
  ...(canSeeUsers ? [{ id: 'users', label: 'Người dùng' }] : []),
];
```

Add `{tab === 'labeling' && <LabelingPage />}` in content area (LabelingPage created in Task 5).

**Step 5: Commit**

```bash
git add backend/app/auth.py backend/app/routers/users.py \
        frontend/src/components/UsersPage.jsx frontend/src/components/UsersPage.css \
        frontend/src/App.jsx
git commit -m "feat: add chuyen_gia role and update tab permissions"
```

---

## Task 2: Role request models + migration

**Files:**
- Create: `backend/app/models/role_request.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/scripts/migrate_labeling_tables.py`

**Step 1: Create RoleRequest model**

```python
# backend/app/models/role_request.py
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RoleRequest(Base):
    __tablename__ = "role_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    requested_role = Column(String(20), nullable=False, default="chuyen_gia")
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/rejected
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
```

**Step 2: Register in `__init__.py`**

Add: `from app.models.role_request import RoleRequest`
Add `"RoleRequest"` to `__all__`.

**Step 3: Create labeling tables migration script**

```python
# backend/scripts/migrate_labeling_tables.py
"""Run once to create labeling tables. python scripts/migrate_labeling_tables.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
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
```

**Step 4: Commit**

```bash
git add backend/app/models/role_request.py backend/app/models/__init__.py \
        backend/scripts/migrate_labeling_tables.py
git commit -m "feat: add RoleRequest model and labeling migration script"
```

---

## Task 3: Labeling data models

**Files:**
- Create: `backend/app/models/label_assignment.py`
- Create: `backend/app/models/label_submission.py`
- Create: `backend/app/models/label_annotation.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: LabelAssignment**

```python
# backend/app/models/label_assignment.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class LabelAssignment(Base):
    """Optional: admin/expert assigns an article to a specific labeler."""
    __tablename__ = "label_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    labeler_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    blind_mode = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: LabelSubmission**

```python
# backend/app/models/label_submission.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class LabelSubmission(Base):
    """One labeler's annotation session for one article."""
    __tablename__ = "label_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    labeler_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft")  # draft | submitted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    annotations = relationship("LabelAnnotation", back_populates="submission",
                                cascade="all, delete-orphan")
```

**Step 3: LabelAnnotation**

```python
# backend/app/models/label_annotation.py
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class LabelAnnotation(Base):
    """Single entity annotation within a submission."""
    __tablename__ = "label_annotations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id = Column(String(36), ForeignKey("label_submissions.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    surface_text = Column(String(500), nullable=True)  # denormalized for display
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("LabelSubmission", back_populates="annotations")
```

**Step 4: Register all three in `__init__.py`**

```python
from app.models.label_assignment import LabelAssignment
from app.models.label_submission import LabelSubmission
from app.models.label_annotation import LabelAnnotation
```

Add all to `__all__`.

**Step 5: Commit**

```bash
git add backend/app/models/label_assignment.py backend/app/models/label_submission.py \
        backend/app/models/label_annotation.py backend/app/models/__init__.py
git commit -m "feat: add LabelAssignment, LabelSubmission, LabelAnnotation models"
```

---

## Task 4: Labeling + Role-request backend routers

**Files:**
- Create: `backend/app/routers/labeling.py`
- Create: `backend/app/routers/role_requests.py`
- Modify: `backend/app/main.py`

**Step 1: Create labeling router**

```python
# backend/app/routers/labeling.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
    )
    subs = subs_result.scalars().all()

    out = []
    for sub in subs:
        # blind mode: labeler only sees own submission
        if blind and sub.labeler_id != user.id:
            continue

        ann_result = await db.execute(
            select(LabelAnnotation).where(LabelAnnotation.submission_id == sub.id)
        )
        annotations = ann_result.scalars().all()

        # get labeler display name
        labeler = await db.get(User, sub.labeler_id)

        out.append(SubmissionOut(
            submission_id=sub.id,
            labeler_id=sub.labeler_id,
            labeler_name=labeler.display_name or labeler.username if labeler else sub.labeler_id[:8],
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
                for ann in annotations
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

    # Delete old annotations and replace
    old = await db.execute(
        select(LabelAnnotation).where(LabelAnnotation.submission_id == sub.id)
    )
    for ann in old.scalars().all():
        await db.delete(ann)

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
    _: User = Depends(require_expert_or_admin),
):
    """Admin or expert assigns an article to a labeler."""
    existing = await db.execute(
        select(LabelAssignment)
        .where(LabelAssignment.article_id == request.article_id)
        .where(LabelAssignment.labeler_id == request.labeler_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Đã được assign trước đó")

    assigner_result = await db.execute(
        select(User).where(User.id == request.labeler_id)
    )
    if not assigner_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Labeler không tồn tại")

    assignment = LabelAssignment(
        article_id=request.article_id,
        labeler_id=request.labeler_id,
        assigned_by="system",  # overridden below
        blind_mode=request.blind_mode,
    )
    db.add(assignment)
    await db.commit()
    return {"status": "assigned"}


@router.patch("/assignments/{assignment_id}/blind-mode")
async def toggle_blind_mode(
    assignment_id: str,
    blind_mode: bool,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_expert_or_admin),
):
    """Toggle blind mode for a specific assignment."""
    a = await db.get(LabelAssignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment không tồn tại")
    a.blind_mode = blind_mode
    await db.commit()
    return {"assignment_id": assignment_id, "blind_mode": blind_mode}
```

**Step 2: Create role_requests router**

```python
# backend/app/routers/role_requests.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.role_request import RoleRequest
from app.auth import get_current_user, require_admin

router = APIRouter()


class RequestRoleResponse(BaseModel):
    id: str
    user_id: str
    username: str
    display_name: str | None
    status: str
    created_at: str


@router.post("/request")
async def request_role_upgrade(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Labeler requests upgrade to chuyen_gia."""
    if user.role != "labeler":
        raise HTTPException(status_code=400, detail="Chỉ labeler mới có thể xin nâng quyền")

    # Check existing pending request
    existing = await db.execute(
        select(RoleRequest)
        .where(RoleRequest.user_id == user.id)
        .where(RoleRequest.status == "pending")
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Đã có yêu cầu đang chờ duyệt")

    req = RoleRequest(user_id=user.id, requested_role="chuyen_gia")
    db.add(req)
    await db.commit()
    return {"message": "Đã gửi yêu cầu nâng quyền"}


@router.get("", response_model=list[RequestRoleResponse])
async def list_role_requests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: list all pending role requests."""
    result = await db.execute(
        select(RoleRequest, User)
        .join(User, RoleRequest.user_id == User.id)
        .where(RoleRequest.status == "pending")
        .order_by(RoleRequest.created_at)
    )
    rows = result.all()
    return [
        RequestRoleResponse(
            id=req.id,
            user_id=req.user_id,
            username=user.username,
            display_name=user.display_name,
            status=req.status,
            created_at=str(req.created_at),
        )
        for req, user in rows
    ]


@router.patch("/{request_id}/approve")
async def approve_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = await db.get(RoleRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu đã được xử lý")

    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    user = await db.get(User, req.user_id)
    if user:
        user.role = req.requested_role

    await db.commit()
    return {"status": "approved"}


@router.patch("/{request_id}/reject")
async def reject_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = await db.get(RoleRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu đã được xử lý")

    req.status = "rejected"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "rejected"}
```

**Step 3: Register both routers in main.py**

```python
from app.routers import crawler, pipeline, ner, admin, feedback, auth, users, labeling, role_requests
# ...
app.include_router(labeling.router, prefix="/api/labeling", tags=["Labeling"])
app.include_router(role_requests.router, prefix="/api/role-requests", tags=["RoleRequests"])
```

**Step 4: Commit**

```bash
git add backend/app/routers/labeling.py backend/app/routers/role_requests.py backend/app/main.py
git commit -m "feat: add labeling and role-requests routers"
```

---

## Task 5: Update api.js with labeling endpoints

**Files:**
- Modify: `frontend/src/services/api.js`

**Step 1: Add new functions before `export default api`**

```js
// Labeling
export const getLabelingArticles = async () => {
  const response = await api.get('/api/labeling/articles');
  return response.data;
};

export const getArticleSubmissions = async (articleId) => {
  const response = await api.get(`/api/labeling/articles/${articleId}/submissions`);
  return response.data;
};

export const saveSubmission = async (articleId, annotations, submit = false) => {
  const response = await api.post(`/api/labeling/articles/${articleId}/save`, {
    annotations,
    submit,
  });
  return response.data;
};

export const assignArticle = async (articleId, labelerId, blindMode = false) => {
  const response = await api.post('/api/labeling/assign', {
    article_id: articleId,
    labeler_id: labelerId,
    blind_mode: blindMode,
  });
  return response.data;
};

// Role requests
export const requestRoleUpgrade = async () => {
  const response = await api.post('/api/role-requests/request');
  return response.data;
};

export const getRoleRequests = async () => {
  const response = await api.get('/api/role-requests');
  return response.data;
};

export const approveRoleRequest = async (requestId) => {
  const response = await api.patch(`/api/role-requests/${requestId}/approve`);
  return response.data;
};

export const rejectRoleRequest = async (requestId) => {
  const response = await api.patch(`/api/role-requests/${requestId}/reject`);
  return response.data;
};
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add labeling and role-request API functions"
```

---

## Task 6: LabelingPage — article list view

**Files:**
- Create: `frontend/src/components/LabelingPage.jsx`
- Create: `frontend/src/components/LabelingPage.css`

**Step 1: Create LabelingPage.jsx (list view only, no annotation UI yet)**

```jsx
// frontend/src/components/LabelingPage.jsx
import React, { useState, useEffect } from 'react';
import { getLabelingArticles } from '../services/api';
import AnnotationView from './AnnotationView';
import './LabelingPage.css';

export default function LabelingPage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null); // article_id being annotated

  useEffect(() => {
    getLabelingArticles()
      .then(setArticles)
      .catch(() => setArticles([]))
      .finally(() => setLoading(false));
  }, []);

  if (selected) {
    return (
      <AnnotationView
        articleId={selected}
        onBack={() => setSelected(null)}
      />
    );
  }

  const STATUS_LABEL = {
    submitted: 'Đã nộp',
    draft: 'Đang làm',
  };

  return (
    <div className="labeling-page">
      <div className="labeling-header">
        <h2 className="labeling-title">Danh sách bài cần gán nhãn</h2>
        <span className="labeling-count">{articles.length} bài</span>
      </div>

      {loading && <p className="labeling-loading">Đang tải...</p>}

      <div className="labeling-table-wrap">
        <table className="labeling-table">
          <thead>
            <tr>
              <th>Tiêu đề / URL</th>
              <th>Labelers</th>
              <th>Trạng thái của bạn</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.article_id}>
                <td className="labeling-title-cell">
                  {a.assigned_to_me && (
                    <span className="labeling-assigned-badge">Được assign</span>
                  )}
                  <span className="labeling-article-title">
                    {a.title || a.url}
                  </span>
                </td>
                <td className="labeling-count-cell">{a.submission_count}</td>
                <td>
                  {a.my_status ? (
                    <span className={`labeling-status labeling-status--${a.my_status}`}>
                      {STATUS_LABEL[a.my_status]}
                    </span>
                  ) : (
                    <span className="labeling-status labeling-status--none">Chưa làm</span>
                  )}
                </td>
                <td>
                  <button
                    className="labeling-btn"
                    onClick={() => setSelected(a.article_id)}
                  >
                    Label
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

**Step 2: Create LabelingPage.css**

```css
.labeling-page {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.labeling-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.labeling-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-text);
}

.labeling-count {
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.labeling-loading {
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.labeling-table-wrap {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.labeling-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.labeling-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.labeling-table td {
  padding: 11px 16px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
  vertical-align: middle;
}

.labeling-table tr:last-child td { border-bottom: none; }

.labeling-title-cell {
  max-width: 500px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.labeling-article-title {
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 480px;
  display: block;
}

.labeling-assigned-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  width: fit-content;
}

.labeling-count-cell { text-align: center; color: var(--color-text-muted); }

.labeling-status {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}

.labeling-status--submitted { background: #d1fae5; color: #065f46; }
.labeling-status--draft     { background: #fef3c7; color: #92400e; }
.labeling-status--none      { background: var(--color-bg); color: var(--color-text-muted); border: 1px solid var(--color-border); }

.labeling-btn {
  padding: 6px 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.labeling-btn:hover { opacity: 0.9; }
```

**Step 3: Commit**

```bash
git add frontend/src/components/LabelingPage.jsx frontend/src/components/LabelingPage.css
git commit -m "feat: add LabelingPage article list view"
```

---

## Task 7: AnnotationView — inline text annotation UI

**Files:**
- Create: `frontend/src/components/AnnotationView.jsx`
- Create: `frontend/src/components/AnnotationView.css`

**Key behaviors:**
- Fetch article `clean_text` from existing `/api/ner/analyze-text` or add new `GET /api/articles/{id}` endpoint
- Fetch submissions from `GET /api/labeling/articles/{id}/submissions`
- Render text as a single `<pre>` block; overlay spans for annotations
- Mouse select → popup → entity type picker → comment input → Save
- Own annotations: colored, clickable to delete
- Others' annotations: muted color, hover shows tooltip (labeler name + comment)
- Bottom bar: username, "Salvar rascunho" + "Enviar" buttons

**Step 1: Add `GET /api/labeling/articles/{id}` endpoint to labeling.py**

Add to `backend/app/routers/labeling.py`:

```python
class ArticleDetail(BaseModel):
    article_id: int
    title: Optional[str]
    url: str
    clean_text: str


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
```

Add to `api.js`:
```js
export const getLabelingArticle = async (articleId) => {
  const response = await api.get(`/api/labeling/articles/${articleId}`);
  return response.data;
};
```

**Step 2: Create AnnotationView.jsx**

```jsx
// frontend/src/components/AnnotationView.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getLabelingArticle, getArticleSubmissions, saveSubmission } from '../services/api';
import { ENTITY_COLORS } from '../config/entityColors';
import './AnnotationView.css';

// Entity types — import from config
import { ENTITY_TYPES } from '../config/entityConfig';

export default function AnnotationView({ articleId, onBack }) {
  const { user } = useAuth();
  const [article, setArticle] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [myAnnotations, setMyAnnotations] = useState([]); // [{entity_type, start_offset, end_offset, surface_text, comment}]
  const [popup, setPopup] = useState(null); // {x, y, start, end, text}
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);
  const textRef = useRef(null);

  useEffect(() => {
    Promise.all([
      getLabelingArticle(articleId),
      getArticleSubmissions(articleId),
    ]).then(([art, subs]) => {
      setArticle(art);
      setSubmissions(subs);
      // load own draft annotations
      const mine = subs.find((s) => s.labeler_id === user.user_id);
      if (mine) setMyAnnotations(mine.annotations);
    });
  }, [articleId, user.user_id]);

  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;
    if (!textRef.current?.contains(sel.anchorNode)) return;

    const range = sel.getRangeAt(0);
    const text = sel.toString().trim();
    if (!text) return;

    // Calculate char offsets relative to clean_text
    const preText = textRef.current.textContent;
    const beforeRange = document.createRange();
    beforeRange.setStart(textRef.current, 0);
    beforeRange.setEnd(range.startContainer, range.startOffset);
    const start = beforeRange.toString().length;
    const end = start + text.length;

    const rect = range.getBoundingClientRect();
    setPopup({ x: rect.left + window.scrollX, y: rect.bottom + window.scrollY + 8, start, end, text });
    sel.removeAllRanges();
  }, []);

  const handleAddAnnotation = (entityType, comment) => {
    if (!popup) return;
    setMyAnnotations((prev) => [
      ...prev,
      {
        entity_type: entityType,
        start_offset: popup.start,
        end_offset: popup.end,
        surface_text: popup.text,
        comment: comment || null,
      },
    ]);
    setPopup(null);
  };

  const handleRemoveAnnotation = (idx) => {
    setMyAnnotations((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSave = async (submit = false) => {
    setSaving(true);
    try {
      await saveSubmission(articleId, myAnnotations, submit);
      setSaveMsg(submit ? 'Đã nộp!' : 'Đã lưu nháp.');
      setTimeout(() => setSaveMsg(null), 2000);
      if (submit) {
        const subs = await getArticleSubmissions(articleId);
        setSubmissions(subs);
      }
    } catch {
      setSaveMsg('Lỗi lưu.');
    } finally {
      setSaving(false);
    }
  };

  if (!article) return <div className="av-loading">Đang tải...</div>;

  const othersAnnotations = submissions
    .filter((s) => s.labeler_id !== user.user_id)
    .flatMap((s) => s.annotations.map((a) => ({ ...a, labeler_name: s.labeler_name })));

  return (
    <div className="av-page">
      <div className="av-topbar">
        <button className="av-back-btn" onClick={onBack}>← Quay lại</button>
        <h2 className="av-article-title">{article.title || article.url}</h2>
      </div>

      <div className="av-text-wrap" ref={textRef} onMouseUp={handleMouseUp}>
        <AnnotatedText
          text={article.clean_text}
          myAnnotations={myAnnotations}
          othersAnnotations={othersAnnotations}
          onRemove={handleRemoveAnnotation}
        />
      </div>

      {popup && (
        <EntityPopupLabeling
          popup={popup}
          onConfirm={handleAddAnnotation}
          onCancel={() => setPopup(null)}
        />
      )}

      <div className="av-bottombar">
        <span className="av-user-info">{user.display_name || user.username}</span>
        {saveMsg && <span className="av-save-msg">{saveMsg}</span>}
        <div className="av-actions">
          <button className="av-btn av-btn--draft" onClick={() => handleSave(false)} disabled={saving}>
            Lưu nháp
          </button>
          <button className="av-btn av-btn--submit" onClick={() => handleSave(true)} disabled={saving}>
            Nộp
          </button>
        </div>
      </div>
    </div>
  );
}
```

Note: `AnnotatedText` and `EntityPopupLabeling` are helper components to render highlighted spans and the entity type popup. Implement them in the same file or as separate files.

**Step 3: Create AnnotationView.css** (dark text area, sticky bottom bar)

```css
.av-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  margin-top: 16px;
}

.av-topbar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
}

.av-back-btn {
  padding: 6px 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: 6px;
  font-size: 0.88rem;
  cursor: pointer;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.av-back-btn:hover { color: var(--color-text); }

.av-article-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.av-text-wrap {
  flex: 1;
  overflow-y: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px 24px;
  font-size: 0.95rem;
  line-height: 2;
  color: var(--color-text);
  user-select: text;
  cursor: text;
  white-space: pre-wrap;
  word-break: break-word;
}

.av-bottombar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--color-border);
  margin-top: 8px;
}

.av-user-info {
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.av-save-msg {
  font-size: 0.85rem;
  color: #16a34a;
}

.av-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.av-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
}

.av-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.av-btn--draft { background: var(--color-surface); border: 1px solid var(--color-border-strong); color: var(--color-text-muted); }
.av-btn--submit { background: var(--color-primary); color: #fff; }

/* Annotation spans */
.av-span-mine {
  border-radius: 3px;
  padding: 1px 0;
  cursor: pointer;
  border-bottom: 2px solid;
}

.av-span-other {
  border-radius: 3px;
  padding: 1px 0;
  opacity: 0.4;
  border-bottom: 2px dashed;
  cursor: default;
  position: relative;
}

/* Entity popup */
.av-popup {
  position: fixed;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.12);
  z-index: 1000;
  min-width: 220px;
}

.av-popup-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.av-popup-types {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.av-type-btn {
  padding: 4px 10px;
  border: 1.5px solid;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  background: transparent;
}

.av-popup-comment {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 0.85rem;
  margin-bottom: 8px;
  font-family: inherit;
  resize: none;
  background: var(--color-bg);
  color: var(--color-text);
  outline: none;
}

.av-popup-actions {
  display: flex;
  justify-content: flex-end;
}

.av-popup-cancel {
  padding: 5px 12px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 0.82rem;
  cursor: pointer;
  color: var(--color-text-muted);
}
```

**Step 4: Commit**

```bash
git add frontend/src/components/AnnotationView.jsx frontend/src/components/AnnotationView.css \
        backend/app/routers/labeling.py frontend/src/services/api.js
git commit -m "feat: add AnnotationView inline text annotation UI"
```

---

## Task 8: "Xin Cấp Quyền" button in nav + admin approval in Users tab

**Files:**
- Modify: `frontend/src/App.jsx` (add button for labeler)
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/components/UsersPage.jsx` (add role requests section)

**Step 1: Add "Xin Cấp Quyền" button to nav for labeler**

In `App.jsx`, in `.tab-nav-user` div, add for labeler role:

```jsx
{user.role === 'labeler' && (
  <button className="tab-nav-upgrade-btn" onClick={handleRequestUpgrade}>
    Xin Cấp Quyền
  </button>
)}
```

Add handler:
```jsx
const [upgradeMsg, setUpgradeMsg] = useState(null);

const handleRequestUpgrade = async () => {
  try {
    await requestRoleUpgrade();
    setUpgradeMsg('Đã gửi yêu cầu!');
    setTimeout(() => setUpgradeMsg(null), 3000);
  } catch (err) {
    setUpgradeMsg(err.response?.data?.detail || 'Lỗi gửi yêu cầu.');
    setTimeout(() => setUpgradeMsg(null), 3000);
  }
};
```

**Step 2: Add role requests section to UsersPage**

At bottom of `UsersPage.jsx`, add a new section that:
- Fetches pending role requests via `getRoleRequests()`
- Shows table: username, display name, requested role, date
- Per row: Duyệt / Từ chối buttons → `approveRoleRequest` / `rejectRoleRequest`
- On approve/reject: remove from list

**Step 3: Commit**

```bash
git add frontend/src/App.jsx frontend/src/App.css frontend/src/components/UsersPage.jsx
git commit -m "feat: add role upgrade request button and admin approval in UsersPage"
```

---

## Task 9: Run migration and verify end-to-end

**Step 1: Run migration**
```bash
cd backend && python scripts/migrate_labeling_tables.py
```
Expected: "All labeling tables created."

**Step 2: Restart backend**
```bash
uvicorn app.main:app --reload
```

**Step 3: Test article list**
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/labeling/articles
```
Expected: JSON array of articles.

**Step 4: Start frontend and verify**
```bash
cd frontend && npm run dev
```
- Login as labeler → see "Labeling" tab
- Click "Label" on any article → see annotation view
- Login as chuyen_gia → also see "Pipeline" and "Duyệt nhãn"
- Login as admin → see all tabs including "Người dùng" with role requests section

**Step 5: Commit migration script**
```bash
git add backend/scripts/migrate_labeling_tables.py
git commit -m "feat: add labeling system migration and verify end-to-end"
```
