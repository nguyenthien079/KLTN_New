# Next Session: Implement Labeling System

**Full plan:** `docs/plans/2026-04-12-labeling-system.md`
**Status:** Not started — all 9 tasks pending.

---

## Quick-start checklist

### Task 1 — `chuyen_gia` role (5 files)
- [ ] `backend/app/auth.py` — add `require_expert_or_admin()` after `require_admin()`
- [ ] `backend/app/routers/users.py` — allow `"chuyen_gia"` in role validation
- [ ] `frontend/src/components/UsersPage.jsx` — add `<option value="chuyen_gia">` + update `ROLE_LABEL`
- [ ] `frontend/src/components/UsersPage.css` — add `.users-role-badge--chuyen_gia`
- [ ] `frontend/src/App.jsx` — update tabs: canSeePipeline/canSeeReview = admin|chuyen_gia; add Labeling tab + `{tab === 'labeling' && <LabelingPage />}`

### Task 2 — RoleRequest model + migration script
- [ ] `backend/app/models/role_request.py` — new model
- [ ] `backend/app/models/__init__.py` — register RoleRequest
- [ ] `backend/scripts/migrate_labeling_tables.py` — `create_all` for labeling tables

### Task 3 — Labeling DB models
- [ ] `backend/app/models/label_assignment.py`
- [ ] `backend/app/models/label_submission.py`
- [ ] `backend/app/models/label_annotation.py`
- [ ] `backend/app/models/__init__.py` — register all three

### Task 4 — Backend routers
- [ ] `backend/app/routers/labeling.py` — GET /articles, GET /articles/{id}, GET /articles/{id}/submissions, POST /articles/{id}/save, POST /assign
- [ ] `backend/app/routers/role_requests.py` — POST /request, GET "", PATCH /{id}/approve, PATCH /{id}/reject
- [ ] `backend/app/main.py` — include both routers

### Task 5 — api.js
- [ ] Add: `getLabelingArticles`, `getLabelingArticle`, `getArticleSubmissions`, `saveSubmission`, `assignArticle`
- [ ] Add: `requestRoleUpgrade`, `getRoleRequests`, `approveRoleRequest`, `rejectRoleRequest`

### Task 6 — LabelingPage (article list)
- [ ] `frontend/src/components/LabelingPage.jsx`
- [ ] `frontend/src/components/LabelingPage.css`

### Task 7 — AnnotationView (inline annotation UI)
- [ ] `frontend/src/components/AnnotationView.jsx` — mouse-select → popup → entity type picker; own vs others' spans
- [ ] `frontend/src/components/AnnotationView.css`

### Task 8 — "Xin Cấp Quyền" + admin approval
- [ ] `frontend/src/App.jsx` — add upgrade button for labeler in nav + `handleRequestUpgrade`
- [ ] `frontend/src/App.css` — add `.tab-nav-upgrade-btn`
- [ ] `frontend/src/components/UsersPage.jsx` — add Role Requests section at bottom

### Task 9 — Run migration + verify
- [ ] `cd backend && python scripts/migrate_labeling_tables.py`
- [ ] Smoke test: login as labeler → Labeling tab; login as chuyen_gia → Pipeline + Duyệt nhãn

---

## Key design decisions (from design session)
- **Blind mode** default OFF — labelers can see each other's annotations
- **Annotation format:** `{entity_type, start_offset, end_offset, surface_text, comment}` on `article.clean_text`
- **Submit flow:** draft → submitted; chuyên gia reviews submissions (not auto-approve)
- **"Hoàn thành review" export** — DEFERRED, user will decide later
- **Entity types** from `frontend/src/config/entityConfig.js`: DISEASE, DRUG, SYMPTOM, TREATMENT, BODY_PART, TEST
- **Entity colors** from `frontend/src/config/entityColors.js`

## Important notes
- `user.user_id` in localStorage (not `user.id`) — check AuthContext when comparing labeler_id
- Article model has `clean_text` column (may be None — default to "")
- `create_all` won't alter existing tables — only use for new tables
- DB: `medical_ner` (1240 articles) — correct DB, already in `.env`
