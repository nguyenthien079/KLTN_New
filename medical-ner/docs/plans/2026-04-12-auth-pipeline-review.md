# Auth + Pipeline + Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add JWT auth (admin/labeler roles), Pipeline tab (filter quality + run pipeline with live logs), Review tab (admin approves labeler submissions), and Users tab (admin manages users).

**Architecture:** Simple JWT auth via `python-jose` + `passlib`; role stored in token claims. Frontend stores JWT in localStorage, passes as `Authorization: Bearer` header. Tab visibility gated by role in React. No changes to existing NER or Crawl functionality.

**Tech Stack:** FastAPI, SQLAlchemy async, python-jose[cryptography], passlib[bcrypt], React, CSS variables (existing design system)

---

## Permission Matrix

| Tab | Labeler | Admin |
|---|---|---|
| Phân tích NER | ✓ | ✓ |
| Thu thập dữ liệu | ✓ | ✓ |
| Pipeline | ✓ | ✓ |
| Review | ✗ | ✓ |
| Quản lý người dùng | ✗ | ✓ |

## Correction status flow

```
Labeler submit → pending_review → Admin: confirm → confirmed (ground truth)
                                            reject → rejected
```

---

## Task 1: Add auth dependencies to requirements.txt

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add two lines under `# Utilities`**

```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

**Step 2: Install in dev environment**

```bash
cd backend && pip install python-jose[cryptography]==3.3.0 passlib[bcrypt]==1.7.4
```

Expected: packages install without errors.

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add python-jose and passlib for JWT auth"
```

---

## Task 2: User model

**Files:**
- Create: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create user model**

```python
# backend/app/models/user.py
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.database import Base
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="labeler")  # "admin" | "labeler"
    display_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: Register model in `__init__.py`**

Read `backend/app/models/__init__.py` first, then add:
```python
from app.models.user import User
```

**Step 3: Commit**

```bash
git add backend/app/models/user.py backend/app/models/__init__.py
git commit -m "feat: add User model with role field"
```

---

## Task 3: Update Correction model

**Files:**
- Modify: `backend/app/models/correction.py`

**Step 1: Add labeler_id and status fields**

Current model has: id, original_text, original_entities, corrected_entities, created_at.

Add after `created_at`:
```python
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
# ...
labeler_id = Column(String(36), ForeignKey("users.id"), nullable=True)
status = Column(String(20), nullable=False, default="pending_review")
# status: "pending_review" | "confirmed" | "rejected"
```

**Step 2: Commit**

```bash
git add backend/app/models/correction.py
git commit -m "feat: add labeler_id and status to Correction model"
```

---

## Task 4: Auth utilities

**Files:**
- Create: `backend/app/auth.py`

**Step 1: Create auth.py**

```python
# backend/app/auth.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User

SECRET_KEY = "change-me-in-production-use-env-var"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token không hợp lệ")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Người dùng không tồn tại")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền này")
    return user
```

**Step 2: Commit**

```bash
git add backend/app/auth.py
git commit -m "feat: add JWT auth utilities"
```

---

## Task 5: Auth router

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`

**Step 1: Create auth router**

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    display_name: str | None
    role: str


class MeResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    token = create_access_token({"sub": user.id, "role": user.role})
    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return MeResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )
```

**Step 2: Register router in main.py**

Add import:
```python
from app.routers import crawler, pipeline, ner, admin, feedback, auth
```

Add router line after existing routers:
```python
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
```

**Step 3: Commit**

```bash
git add backend/app/routers/auth.py backend/app/main.py
git commit -m "feat: add auth router with login and /me endpoints"
```

---

## Task 6: Users router (admin)

**Files:**
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`

**Step 1: Create users router**

```python
# backend/app/routers/users.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.auth import hash_password, require_admin

router = APIRouter()


class UserResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    role: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "labeler"


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [
        UserResponse(
            user_id=u.id,
            username=u.username,
            display_name=u.display_name,
            role=u.role,
        )
        for u in users
    ]


@router.post("", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.username == request.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")

    if request.role not in ("admin", "labeler"):
        raise HTTPException(status_code=400, detail="Role phải là admin hoặc labeler")

    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
        display_name=request.display_name,
        role=request.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )
```

**Step 2: Register in main.py**

```python
from app.routers import crawler, pipeline, ner, admin, feedback, auth, users
# ...
app.include_router(users.router, prefix="/api/users", tags=["Users"])
```

**Step 3: Commit**

```bash
git add backend/app/routers/users.py backend/app/main.py
git commit -m "feat: add users router for admin user management"
```

---

## Task 7: Seed admin user script

**Files:**
- Create: `backend/scripts/seed_admin.py`

**Step 1: Create seed script**

```python
# backend/scripts/seed_admin.py
"""Run once: python scripts/seed_admin.py"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth import hash_password


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Admin already exists")
            return

        user = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            display_name="Administrator",
            role="admin",
        )
        db.add(user)
        await db.commit()
        print("Created admin user: admin / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
```

**Step 2: Commit**

```bash
git add backend/scripts/seed_admin.py
git commit -m "feat: add seed_admin script"
```

---

## Task 8: Update feedback router for review workflow

**Files:**
- Modify: `backend/app/routers/feedback.py`

**Step 1: Update SubmitRequest schema to include status**

In `CorrectionItem`, add optional field:
```python
class CorrectionItem(BaseModel):
    original_text: str
    original_entities: List[EntityItem]
    corrected_entities: List[EntityItem]
    status: str = "pending_review"
```

**Step 2: Update submit_corrections to save labeler_id and status**

Change the correction creation in the loop:
```python
correction = Correction(
    original_text=item.original_text,
    original_entities=[e.model_dump() for e in item.original_entities],
    corrected_entities=[e.model_dump() for e in item.corrected_entities],
    status=item.status,
    # labeler_id set by auth in next step
)
```

**Step 3: Add review endpoints**

Add these after the existing endpoints:

```python
from app.auth import get_current_user, require_admin
from app.models.user import User


class ReviewResponse(BaseModel):
    id: str
    original_text: str
    original_entities: list
    corrected_entities: list
    status: str
    labeler_id: str | None


@router.get("/queue", response_model=list[ReviewResponse])
async def get_review_queue(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: list all corrections"""
    result = await db.execute(
        select(Correction).order_by(Correction.created_at.desc())
    )
    corrections = result.scalars().all()
    return [
        ReviewResponse(
            id=c.id,
            original_text=c.original_text,
            original_entities=c.original_entities,
            corrected_entities=c.corrected_entities,
            status=c.status,
            labeler_id=c.labeler_id,
        )
        for c in corrections
    ]


@router.patch("/{correction_id}/confirm")
async def confirm_correction(
    correction_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Correction).where(Correction.id == correction_id))
    corr = result.scalar_one_or_none()
    if not corr:
        raise HTTPException(status_code=404, detail="Không tìm thấy")
    corr.status = "confirmed"
    await db.commit()
    return {"id": correction_id, "status": "confirmed"}


@router.patch("/{correction_id}/reject")
async def reject_correction(
    correction_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Correction).where(Correction.id == correction_id))
    corr = result.scalar_one_or_none()
    if not corr:
        raise HTTPException(status_code=404, detail="Không tìm thấy")
    corr.status = "rejected"
    await db.commit()
    return {"id": correction_id, "status": "rejected"}
```

**Step 4: Commit**

```bash
git add backend/app/routers/feedback.py
git commit -m "feat: add review queue and confirm/reject endpoints"
```

---

## Task 9: Pipeline filter endpoint

**Files:**
- Modify: `backend/app/routers/pipeline.py`

**Step 1: Add filter_jobs dict and new endpoints**

Add at top of file:
```python
filter_jobs: dict = {}
```

Add new endpoint after existing ones:

```python
@router.post("/filter")
async def start_filter(background_tasks: BackgroundTasks):
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
```

**Step 2: Update run_pipeline_job to emit logs**

Replace existing `run_pipeline_job` with version that logs progress. Add `logs` to job dict:

```python
pipeline_jobs[job_id] = {
    "status": "running",
    "article_id": request.article_id,
    "articles_processed": 0,
    "total_sentences": 0,
    "logs": [],
}
```

In `run_pipeline_job`, add before stats call:
```python
pipeline_jobs[job_id]["logs"].append("Đang khởi động pipeline...")
```

After completion:
```python
pipeline_jobs[job_id]["logs"].append(
    f"Hoàn tất: {stats['articles_processed']} bài, {stats['total_sentences']} câu"
)
```

**Step 3: Commit**

```bash
git add backend/app/routers/pipeline.py
git commit -m "feat: add filter endpoint and logs to pipeline jobs"
```

---

## Task 10: Frontend — Auth context and Login page

**Files:**
- Create: `frontend/src/contexts/AuthContext.jsx`
- Create: `frontend/src/components/LoginPage.jsx`
- Create: `frontend/src/components/LoginPage.css`

**Step 1: Create AuthContext**

```jsx
// frontend/src/contexts/AuthContext.jsx
import React, { createContext, useContext, useState, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('auth_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const login = useCallback((userData) => {
    localStorage.setItem('auth_user', JSON.stringify(userData));
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_user');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
```

**Step 2: Create LoginPage.jsx**

```jsx
// frontend/src/components/LoginPage.jsx
import React, { useState } from 'react';
import { loginUser } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import './LoginPage.css';

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Vui lòng nhập đầy đủ thông tin.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await loginUser(username.trim(), password);
      login(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Đăng nhập thất bại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">Medical NER</h1>
        <p className="login-subtitle">Hệ thống nhận diện thực thể y tế</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-field">
            <label className="login-label">Tên đăng nhập</label>
            <input
              className="login-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
            />
          </div>
          <div className="login-field">
            <label className="login-label">Mật khẩu</label>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          {error && <p className="login-error">{error}</p>}
          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
      </div>
    </div>
  );
}
```

**Step 3: Create LoginPage.css** — match existing design system

```css
/* frontend/src/components/LoginPage.css */
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 36px 32px;
  box-shadow: var(--shadow-sm);
}

.login-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: 4px;
}

.login-subtitle {
  font-size: 0.88rem;
  color: var(--color-text-muted);
  margin-bottom: 28px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.login-label {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-text);
}

.login-input {
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.95rem;
  background: var(--color-bg);
  color: var(--color-text);
  outline: none;
  transition: border-color 0.15s;
}

.login-input:focus {
  border-color: var(--color-primary);
}

.login-error {
  color: var(--color-error, #dc2626);
  font-size: 0.88rem;
}

.login-btn {
  padding: 11px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
```

**Step 4: Commit**

```bash
git add frontend/src/contexts/AuthContext.jsx frontend/src/components/LoginPage.jsx frontend/src/components/LoginPage.css
git commit -m "feat: add AuthContext and LoginPage"
```

---

## Task 11: Update api.js — auth header + new endpoints

**Files:**
- Modify: `frontend/src/services/api.js`

**Step 1: Add token injection interceptor and new functions**

After the `api` instance creation, add interceptor:
```js
api.interceptors.request.use((config) => {
  try {
    const stored = localStorage.getItem('auth_user');
    if (stored) {
      const { access_token } = JSON.parse(stored);
      if (access_token) {
        config.headers.Authorization = `Bearer ${access_token}`;
      }
    }
  } catch {}
  return config;
});
```

Add new exported functions:
```js
export const loginUser = async (username, password) => {
  const response = await api.post('/api/auth/login', { username, password });
  return response.data;
};

export const getUsers = async () => {
  const response = await api.get('/api/users');
  return response.data;
};

export const createUser = async (data) => {
  const response = await api.post('/api/users', data);
  return response.data;
};

export const getReviewQueue = async () => {
  const response = await api.get('/api/feedback/queue');
  return response.data;
};

export const confirmCorrection = async (id) => {
  const response = await api.patch(`/api/feedback/${id}/confirm`);
  return response.data;
};

export const rejectCorrection = async (id) => {
  const response = await api.patch(`/api/feedback/${id}/reject`);
  return response.data;
};

export const startFilter = async () => {
  const response = await api.post('/api/pipeline/filter');
  return response.data;
};

export const getFilterStatus = async (jobId) => {
  const response = await api.get(`/api/pipeline/filter/${jobId}`);
  return response.data;
};

export const getPipelineStatus = async (jobId) => {
  const response = await api.get(`/api/pipeline/status/${jobId}`);
  return response.data;
};

export const startPipeline = async () => {
  const response = await api.post('/api/pipeline/process', {});
  return response.data;
};
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add auth interceptor and new API functions"
```

---

## Task 12: Frontend — PipelinePage

**Files:**
- Create: `frontend/src/components/PipelinePage.jsx`
- Create: `frontend/src/components/PipelinePage.css`

**Step 1: Create PipelinePage.jsx**

Two sections, each with a button, real-time log terminal, and status badge — reusing the same polling pattern as CrawlPage.

```jsx
// frontend/src/components/PipelinePage.jsx
import React, { useState, useEffect, useRef } from 'react';
import { startFilter, getFilterStatus, startPipeline, getPipelineStatus } from '../services/api';
import './PipelinePage.css';

function JobSection({ title, description, onStart, pollFn }) {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const logRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => {
    if (!jobId) return;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await pollFn(jobId);
        setStatus(data.status);
        setLogs(data.logs || []);
        if (data.result) setResult(data.result);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current);
        }
      } catch {
        clearInterval(pollRef.current);
        setStatus('failed');
      }
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [jobId, pollFn]);

  const handleStart = async () => {
    setError(null);
    setLogs([]);
    setResult(null);
    setStatus('running');
    try {
      const data = await onStart();
      setJobId(data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu.');
    }
  };

  return (
    <div className="pipeline-section">
      <div className="pipeline-section-header">
        <div>
          <h3 className="pipeline-section-title">{title}</h3>
          <p className="pipeline-section-desc">{description}</p>
        </div>
        <button
          className="pipeline-btn"
          onClick={handleStart}
          disabled={status === 'running'}
        >
          {status === 'running' ? 'Đang chạy...' : 'Chạy'}
        </button>
      </div>

      {error && <p className="pipeline-error">{error}</p>}

      {status && (
        <>
          <div className="pipeline-status-row">
            <span className={`pipeline-badge pipeline-badge--${status}`}>
              {status === 'running' && '● Đang chạy'}
              {status === 'completed' && '✓ Hoàn thành'}
              {status === 'failed' && '✗ Lỗi'}
            </span>
            {result && (
              <span className="pipeline-result-summary">
                {Object.entries(result).map(([k, v]) => `${k}: ${v}`).join(' · ')}
              </span>
            )}
          </div>
          <div className="pipeline-log" ref={logRef}>
            {logs.length === 0 && status === 'running' && (
              <span className="pipeline-log-placeholder">Đang khởi động...</span>
            )}
            {logs.map((line, i) => (
              <div key={i} className="pipeline-log-line">{line}</div>
            ))}
            {status === 'completed' && (
              <div className="pipeline-log-line pipeline-log-done">✓ Hoàn tất.</div>
            )}
            {status === 'failed' && (
              <div className="pipeline-log-line pipeline-log-error">✗ Thất bại.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function PipelinePage() {
  return (
    <div className="pipeline-page">
      <JobSection
        title="Lọc chất lượng"
        description="Xóa bài viết quá ngắn (< 200 ký tự), quá dài (> 50 000 ký tự) hoặc quá ít từ (< 20 khoảng trắng)."
        onStart={startFilter}
        pollFn={getFilterStatus}
      />
      <JobSection
        title="Chạy pipeline"
        description="Phân đoạn tất cả bài viết trong database thành câu (MedicalTextPipeline)."
        onStart={startPipeline}
        pollFn={getPipelineStatus}
      />
    </div>
  );
}
```

**Step 2: Create PipelinePage.css** — consistent with CrawlPage.css design

```css
/* frontend/src/components/PipelinePage.css */
.pipeline-page {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pipeline-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pipeline-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.pipeline-section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 4px;
}

.pipeline-section-desc {
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.pipeline-btn {
  padding: 9px 22px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.pipeline-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pipeline-error {
  color: var(--color-error, #dc2626);
  font-size: 0.88rem;
}

.pipeline-status-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pipeline-badge {
  font-size: 0.88rem;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
}

.pipeline-badge--running   { background: #fef3c7; color: #92400e; }
.pipeline-badge--completed { background: #d1fae5; color: #065f46; }
.pipeline-badge--failed    { background: var(--color-error-bg); color: var(--color-error); }

.pipeline-result-summary {
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.pipeline-log {
  background: #0f172a;
  color: #94a3b8;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  border-radius: 6px;
  padding: 14px 16px;
  max-height: 260px;
  overflow-y: auto;
}

.pipeline-log-placeholder {
  color: #475569;
  font-style: italic;
}

.pipeline-log-line { white-space: pre-wrap; word-break: break-all; }
.pipeline-log-done  { color: #4ade80; margin-top: 6px; }
.pipeline-log-error { color: #f87171; margin-top: 6px; }
```

**Step 3: Commit**

```bash
git add frontend/src/components/PipelinePage.jsx frontend/src/components/PipelinePage.css
git commit -m "feat: add PipelinePage with filter and pipeline job sections"
```

---

## Task 13: Frontend — ReviewPage (admin)

**Files:**
- Create: `frontend/src/components/ReviewPage.jsx`
- Create: `frontend/src/components/ReviewPage.css`

**Step 1: Create ReviewPage.jsx**

```jsx
// frontend/src/components/ReviewPage.jsx
import React, { useState, useEffect } from 'react';
import { getReviewQueue, confirmCorrection, rejectCorrection } from '../services/api';
import './ReviewPage.css';

const STATUS_LABEL = {
  pending_review: 'Chờ duyệt',
  confirmed: 'Đã duyệt',
  rejected: 'Từ chối',
};

export default function ReviewPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getReviewQueue();
      setItems(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleConfirm = async (id) => {
    await confirmCorrection(id);
    setItems((prev) => prev.map((x) => x.id === id ? { ...x, status: 'confirmed' } : x));
  };

  const handleReject = async (id) => {
    await rejectCorrection(id);
    setItems((prev) => prev.map((x) => x.id === id ? { ...x, status: 'rejected' } : x));
  };

  if (loading) return <div className="review-loading">Đang tải...</div>;
  if (error) return <div className="review-error">{error}</div>;

  const pending = items.filter((x) => x.status === 'pending_review');
  const done = items.filter((x) => x.status !== 'pending_review');

  return (
    <div className="review-page">
      <div className="review-summary">
        <span className="review-count">{pending.length} chờ duyệt</span>
        <span className="review-count-done">{done.length} đã xử lý</span>
        <button className="review-refresh-btn" onClick={load}>Làm mới</button>
      </div>

      {items.length === 0 && (
        <div className="review-empty">Chưa có dữ liệu gán nhãn nào.</div>
      )}

      <div className="review-list">
        {items.map((item) => (
          <div key={item.id} className={`review-item review-item--${item.status}`}>
            <div className="review-item-header">
              <span className={`review-badge review-badge--${item.status}`}>
                {STATUS_LABEL[item.status] || item.status}
              </span>
              <span className="review-labeler">
                {item.labeler_id ? `Labeler: ${item.labeler_id.slice(0, 8)}` : ''}
              </span>
            </div>

            <p className="review-text">{item.original_text}</p>

            <div className="review-entities">
              <div className="review-entities-col">
                <span className="review-entities-label">Gốc ({item.original_entities.length})</span>
                {item.original_entities.map((e, i) => (
                  <span key={i} className="review-entity-chip review-entity-chip--original">
                    {e.text} <em>{e.type}</em>
                  </span>
                ))}
              </div>
              <div className="review-entities-col">
                <span className="review-entities-label">Đã sửa ({item.corrected_entities.length})</span>
                {item.corrected_entities.map((e, i) => (
                  <span key={i} className="review-entity-chip review-entity-chip--corrected">
                    {e.text} <em>{e.type}</em>
                  </span>
                ))}
              </div>
            </div>

            {item.status === 'pending_review' && (
              <div className="review-actions">
                <button
                  className="review-btn review-btn--confirm"
                  onClick={() => handleConfirm(item.id)}
                >
                  Duyệt
                </button>
                <button
                  className="review-btn review-btn--reject"
                  onClick={() => handleReject(item.id)}
                >
                  Từ chối
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Create ReviewPage.css**

```css
/* frontend/src/components/ReviewPage.css */
.review-page {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.review-summary {
  display: flex;
  align-items: center;
  gap: 16px;
}

.review-count {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-primary);
}

.review-count-done {
  font-size: 0.9rem;
  color: var(--color-text-muted);
}

.review-refresh-btn {
  margin-left: auto;
  padding: 6px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: 6px;
  font-size: 0.88rem;
  cursor: pointer;
  color: var(--color-text-muted);
}

.review-refresh-btn:hover { color: var(--color-text); }

.review-empty {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  padding: 20px 0;
}

.review-loading, .review-error {
  margin-top: 28px;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.review-item--confirmed { border-left: 3px solid #16a34a; }
.review-item--rejected  { border-left: 3px solid #dc2626; }
.review-item--pending_review { border-left: 3px solid var(--color-primary); }

.review-item-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.review-badge {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}

.review-badge--pending_review { background: #fef3c7; color: #92400e; }
.review-badge--confirmed      { background: #d1fae5; color: #065f46; }
.review-badge--rejected       { background: #fee2e2; color: #991b1b; }

.review-labeler {
  font-size: 0.78rem;
  color: var(--color-text-muted);
  margin-left: auto;
}

.review-text {
  font-size: 0.9rem;
  color: var(--color-text);
  line-height: 1.6;
  border-left: 2px solid var(--color-border);
  padding-left: 10px;
}

.review-entities {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.review-entities-col {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.review-entities-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  margin-bottom: 3px;
}

.review-entity-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 0.82rem;
  width: fit-content;
}

.review-entity-chip em {
  font-style: normal;
  font-size: 0.72rem;
  opacity: 0.7;
  text-transform: uppercase;
}

.review-entity-chip--original  { background: #f1f5f9; color: var(--color-text); }
.review-entity-chip--corrected { background: #eff6ff; color: #1d4ed8; }

.review-actions {
  display: flex;
  gap: 8px;
}

.review-btn {
  padding: 7px 18px;
  border: none;
  border-radius: 6px;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
}

.review-btn--confirm { background: #16a34a; color: #fff; }
.review-btn--confirm:hover { background: #15803d; }
.review-btn--reject  { background: var(--color-surface); color: #dc2626; border: 1px solid #fca5a5; }
.review-btn--reject:hover  { background: #fef2f2; }
```

**Step 3: Commit**

```bash
git add frontend/src/components/ReviewPage.jsx frontend/src/components/ReviewPage.css
git commit -m "feat: add ReviewPage for admin to confirm or reject corrections"
```

---

## Task 14: Frontend — UsersPage (admin)

**Files:**
- Create: `frontend/src/components/UsersPage.jsx`
- Create: `frontend/src/components/UsersPage.css`

**Step 1: Create UsersPage.jsx**

```jsx
// frontend/src/components/UsersPage.jsx
import React, { useState, useEffect } from 'react';
import { getUsers, createUser } from '../services/api';
import './UsersPage.css';

const ROLE_LABEL = { admin: 'Admin', labeler: 'Labeler' };

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'labeler' });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      setUsers(await getUsers());
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password.trim()) {
      setCreateError('Vui lòng điền đầy đủ.');
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createUser(form);
      setUsers((prev) => [...prev, created]);
      setForm({ username: '', password: '', display_name: '', role: 'labeler' });
    } catch (err) {
      setCreateError(err.response?.data?.detail || 'Tạo thất bại.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="users-page">
      <div className="users-table-wrap">
        {loading && <p className="users-loading">Đang tải...</p>}
        {error && <p className="users-error">{error}</p>}
        {!loading && !error && (
          <table className="users-table">
            <thead>
              <tr>
                <th>Tên hiển thị</th>
                <th>Tên đăng nhập</th>
                <th>Quyền</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id}>
                  <td>{u.display_name || '—'}</td>
                  <td className="users-username">{u.username}</td>
                  <td>
                    <span className={`users-role-badge users-role-badge--${u.role}`}>
                      {ROLE_LABEL[u.role] || u.role}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="users-create-form-wrap">
        <h3 className="users-create-title">Thêm người dùng</h3>
        <form className="users-create-form" onSubmit={handleCreate}>
          <input
            className="users-input"
            placeholder="Tên đăng nhập *"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <input
            className="users-input"
            placeholder="Mật khẩu *"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <input
            className="users-input"
            placeholder="Tên hiển thị"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
          <select
            className="users-select"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            <option value="labeler">Labeler</option>
            <option value="admin">Admin</option>
          </select>
          {createError && <p className="users-error">{createError}</p>}
          <button className="users-create-btn" type="submit" disabled={creating}>
            {creating ? 'Đang tạo...' : 'Tạo'}
          </button>
        </form>
      </div>
    </div>
  );
}
```

**Step 2: Create UsersPage.css**

```css
/* frontend/src/components/UsersPage.css */
.users-page {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.users-table-wrap {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.users-table th {
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

.users-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
}

.users-table tr:last-child td { border-bottom: none; }

.users-username {
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
}

.users-role-badge {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}

.users-role-badge--admin   { background: #ede9fe; color: #5b21b6; }
.users-role-badge--labeler { background: #e0f2fe; color: #0369a1; }

.users-loading, .users-error {
  padding: 16px;
  font-size: 0.9rem;
  color: var(--color-text-muted);
}

.users-error { color: var(--color-error, #dc2626); }

.users-create-form-wrap {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
}

.users-create-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 14px;
}

.users-create-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.users-input, .users-select {
  padding: 9px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.9rem;
  background: var(--color-bg);
  color: var(--color-text);
  outline: none;
}

.users-input:focus, .users-select:focus { border-color: var(--color-primary); }

.users-create-btn {
  grid-column: 1 / -1;
  padding: 10px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
}

.users-create-btn:disabled { opacity: 0.6; cursor: not-allowed; }
```

**Step 3: Commit**

```bash
git add frontend/src/components/UsersPage.jsx frontend/src/components/UsersPage.css
git commit -m "feat: add UsersPage for admin user management"
```

---

## Task 15: Update App.jsx — auth gate, tab visibility, logout

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/main.jsx` (wrap with AuthProvider)

**Step 1: Wrap app in AuthProvider in main.jsx**

Read `frontend/src/main.jsx`, then add:
```jsx
import { AuthProvider } from './contexts/AuthContext';
// Wrap <App /> with <AuthProvider><App /></AuthProvider>
```

**Step 2: Rewrite App.jsx**

Replace current App.jsx with a version that:
1. Reads `useAuth()` — if `!user`, render `<LoginPage />`
2. Shows tabs based on role: all users see NER + Thu thập + Pipeline; only admin sees Review + Users
3. Shows current user's `display_name || username` + logout button in nav bar

Key nav logic:
```jsx
const tabs = [
  { id: 'ner', label: 'Phân tích NER' },
  { id: 'crawl', label: 'Thu thập dữ liệu' },
  { id: 'pipeline', label: 'Pipeline' },
  ...(user.role === 'admin' ? [
    { id: 'review', label: 'Duyệt nhãn' },
    { id: 'users', label: 'Người dùng' },
  ] : []),
];
```

Add logout button in tab-nav-inner (right side):
```jsx
<div className="tab-nav-user">
  <span className="tab-nav-username">{user.display_name || user.username}</span>
  <button className="tab-nav-logout" onClick={logout}>Đăng xuất</button>
</div>
```

Add to App.css:
```css
.tab-nav-inner { justify-content: flex-start; }
.tab-nav-user {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.tab-nav-username { font-size: 0.85rem; color: var(--color-text-muted); }
.tab-nav-logout {
  padding: 5px 14px;
  background: transparent;
  border: 1px solid var(--color-border-strong);
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
  color: var(--color-text-muted);
}
.tab-nav-logout:hover { color: var(--color-error); border-color: #fca5a5; }
```

**Step 3: Commit**

```bash
git add frontend/src/App.jsx frontend/src/main.jsx frontend/src/App.css
git commit -m "feat: add auth gate, role-based tabs, and logout to App"
```

---

## Task 16: Seed admin and verify end-to-end

**Step 1: Run backend with new models**

```bash
cd backend && uvicorn app.main:app --reload
```

Tables `users` and updated `corrections` will be created automatically via `create_all`.

**Step 2: Seed admin user**

```bash
cd backend && python scripts/seed_admin.py
```

Expected: `Created admin user: admin / admin123`

**Step 3: Test login via API**

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Expected: JSON with `access_token`, `role: "admin"`

**Step 4: Start frontend and verify**

```bash
cd frontend && npm run dev
```

- Visit http://localhost:5173 → should show LoginPage
- Login as admin → should see all 5 tabs
- Create a labeler user via Users tab
- Logout → login as labeler → should see only 3 tabs (no Review, no Người dùng)

**Step 5: Final commit**

```bash
git add backend/scripts/seed_admin.py
git commit -m "feat: complete auth + pipeline + review workflow"
```
