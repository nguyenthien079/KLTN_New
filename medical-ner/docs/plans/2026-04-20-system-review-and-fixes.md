# System Review & Fix Tracker
**Date:** 2026-04-20  
**Scope:** Architectural review + Expert UI audit

---

## Tổng quan hệ thống hiện tại

Hệ thống có **3 subsystem tách biệt, không kết nối**:

| Subsystem | Route | Lưu trữ | Trạng thái |
|-----------|-------|---------|------------|
| A — ML Inference | `/api/ner/*` | Không lưu gì (ephemeral) | Active |
| B — Expert Labeling | `/api/labeling/*` | `label_submissions` + `label_annotations` | Active |
| C — Feedback/Corrections | `/api/feedback/*` | `corrections` (JSON blob) | Active nhưng orphaned |

Batch pipeline (`/api/pipeline/*`) populate riêng `entities` + `knowledge_map` — không liên kết với B hay C.

---

## Phần 1 — Lỗi Kiến Trúc

### A1 — Hai hệ thống annotation song song, không reconcile
**Mức độ:** Critical  
**Vấn đề:**  
- `LabelAnnotation` (Subsystem B) và `Correction` (Subsystem C) đều lưu human annotations nhưng khác schema, khác bảng, không cross-reference.
- Không có canonical ground-truth table.
- `ReviewPage.jsx` gọi hàm tên `confirmCorrection`/`rejectCorrection` nhưng thực ra hit `/api/labeling/review/{id}/confirm|reject` — tức là thao tác trên `LabelSubmission`, không phải `Correction`. Naming mismatch là triệu chứng của sự lẫn lộn khái niệm.

**Fix cần làm:** Gộp thành một unified annotation table duy nhất với:
- `source` (rule / dictionary / phobert / human)
- Lifecycle: `pending → submitted → confirmed / rejected`
- `article_id` + char-level span
- FK tới model prediction gốc (nếu có)

---

### A2 — Confirmed annotation là dead end (vòng phản hồi bị gãy)
**Mức độ:** Critical  
**Vấn đề:**  
Cả Subsystem B (`LabelSubmission.status = "confirmed"`) lẫn C (`Correction.status = "confirmed"`) đều chỉ thay status column rồi dừng. Không có:
- Trigger cập nhật dictionary (`data/dicts/medical_terms.json`)
- Trigger retrain / fine-tune PhoBERT
- Trigger mở rộng rules (`ner/rules.py`)
- Trigger populate lại `Entity` table từ confirmed annotations

Human-in-the-loop workflow **có UI, có state machine, nhưng functionally inert.**

**Fix cần làm:** Định nghĩa contract rõ khi confirm:
1. Surface text chưa có trong dict → candidate dictionary expansion
2. Annotation sửa prediction của nguồn cụ thể → training example cho nguồn đó
3. Accumulate vào retraining queue, flush khi đủ N examples

---

### A3 — Suggestion endpoint dùng pipeline kém hơn live NER
**Mức độ:** High  
**Vấn đề:**  
`/api/labeling/articles/{id}/suggest` gọi `app.ner.pipeline.run()` — chỉ rule + dictionary, **không có PhoBERT**.  
`/api/ner/analyze-text` gọi `MedicalNERPipeline` — có đủ ensemble.  
Expert dùng labeling UI nhận suggestions kém hơn user thường dùng NER tab.

**Fix cần làm:** Suggestion endpoint dùng `MedicalNERPipeline` thay vì `app.ner.pipeline.run()`.

---

### A4 — Review queue ẩn model predictions
**Mức độ:** High  
**Vấn đề:**  
Trong `get_label_review_queue` (`labeling.py` line 469), `original_entities` hardcode `= []`.  
Reviewer thấy "Gốc (0)" ở mọi item → không thể so sánh model predicted vs human labeled.  
Review workflow thu thập status changes nhưng mất đi analytical value.

**Fix cần làm:** Khi expert mở article để label, snapshot model predictions và lưu vào `LabelSubmission`. Review queue hiển thị snapshot đó ở cột "Gốc".

---

### A5 — Entity table và LabelAnnotation table là 2 vũ trụ tách biệt
**Mức độ:** High  
**Vấn đề:**  
- `Entity` + `KnowledgeMap` = ML output
- `LabelAnnotation` = human output  
Không có FK, không có reconciliation. Hệ thống không thể trả lời: "Expert annotation này đang confirm, sửa, hay mâu thuẫn với ML prediction không?"

`/api/admin/stats` đọc từ `Entity` (ML output), không phản ánh confirmed human ground truth.

---

### A6 — BIO export tạo training data sai
**Mức độ:** High  
**Vấn đề:**  
`convert_to_bio` (`feedback.py` line 206) và `DataPreparator.label_sentence` (`data_preparation.py` line 46) đều dùng `text.split()` — whitespace tokenization.  
Tiếng Việt không tách từ bằng space đơn thuần → BIO tags bị misalign với character offsets.  
Fine-tune PhoBERT trên data này có thể **làm model kém đi** so với checkpoint gốc.

**Fix cần làm:** Dùng proper Vietnamese tokenizer (e.g. `underthesea.word_tokenize`) cho BIO conversion.

---

### A7 — Xóa role `labeler`, thiết lập lại role model: `chuyen_gia` (default) và `admin`
**Mức độ:** Medium  

**Role model mới:**
| Role | Ý nghĩa | Đăng ký mặc định |
|------|---------|-----------------|
| `chuyen_gia` | User thường, có thể labeling | ✅ default |
| `admin` | Quản trị hệ thống, duyệt annotations | ❌ phải được cấp |

**Vấn đề hiện tại:**
- Có 3 roles: `admin`, `labeler`, `chuyen_gia` — `labeler` thừa, cần xóa
- `User` model default là `"labeler"`, comment ghi `"admin" | "labeler"` — đều sai
- `RoleRequest.requested_role` default là `"chuyen_gia"` — sẽ phải đổi thành `"admin"`
- `roleTabConfig` trong `App.jsx` có nhánh `labeler` riêng — cần xóa, gộp vào `chuyen_gia`
- Nút "Xin Cấp Quyền" hiện xin lên `chuyen_gia` → đổi thành xin lên `admin`
- Guard `require_expert_or_admin` check `"chuyen_gia"` — rename thành `require_admin` cho rõ nghĩa (vì chuyen_gia là default user, không cần guard riêng)

**Ảnh hưởng cần đụng:**
- `backend/app/models/user.py` — đổi default role thành `"chuyen_gia"`, xóa `labeler`
- `backend/app/models/role_request.py` — đổi `requested_role` default thành `"admin"`
- `backend/app/auth.py` — xóa `require_expert_or_admin`, chỉ giữ `require_admin`; `get_current_user` không cần check labeler nữa
- `backend/app/routers/role_requests.py` — cập nhật target role thành `admin`
- `frontend/src/App.jsx` — xóa nhánh `role === 'labeler'`, gộp tabs vào `chuyen_gia`; đổi label nút thành "Xin Cấp Quyền Admin"
- Migration DB: user nào đang là `labeler` → `UPDATE users SET role = 'chuyen_gia' WHERE role = 'labeler'`

**Fix cần làm:** Giữ đúng 2 roles. `chuyen_gia` là entry point mặc định, `admin` là elevated role được cấp thủ công.

---

## Phần 2 — Lỗi UI (Expert Labeling)

### U1 — Edit annotation bị thiếu trong LabelingPage
**Mức độ:** Medium  
**Vấn đề:**  
Trong `LabelingPage.jsx`, click vào annotation đang highlight → gọi `onRemove(annIndex)` (xóa thẳng). Không có flow sửa type hay comment mà không xóa rồi add lại.

`AnnotationSentence.jsx` có edit đầy đủ (`mode: 'edit'` với popup) nhưng chỉ được dùng trong `ResultsPanel.jsx` (NER tab), không phải labeling.

**Fix cần làm:** Trong `LabelingPage`, click annotation hiện popup với mode edit (pre-select type hiện tại + nút xóa), thay vì xóa ngay.

---

### U2 — AnnotationView.jsx là orphaned component
**Mức độ:** Medium  
**Vấn đề:**  
`AnnotationView.jsx` có UI tốt hơn (hiển thị annotations của người khác, nút "Hoàn thành review", export), nhưng **không được import ở bất kỳ đâu** trong navigation — không có trong `App.jsx`, `LabelingPage.jsx`, `DataListPage.jsx`.

Component này phù hợp hơn cho expert workflow nhưng unreachable.

**Fix cần làm:** Kết nối `AnnotationView` vào `LabelingPage` như single-article detail view, hoặc thêm route trong `App.jsx`.

---

### U3 — Bug offset trong AnnotationView.handleMouseUp
**Mức độ:** Low  
**Vấn đề:**  
```js
// AnnotationView — chỉ check anchorNode (thiếu focusNode)
if (!textRef.current?.contains(sel.anchorNode)) return;

// LabelingPage — check cả hai đầu (đúng)
if (!textRef.current?.contains(sel.anchorNode) || !textRef.current?.contains(sel.focusNode)) return;
```
Kéo selection ra ngoài container → offset tính sai.

Ngoài ra `end = start + rawText.length` dùng độ dài chưa trim → end_offset có thể lệch so với `surface_text` đã trim.

---

## Bảng ưu tiên

| ID | Vấn đề | Mức độ | Phụ thuộc |
|----|--------|--------|-----------|
| A2 | Feedback loop bị gãy | Critical | A1 |
| A1 | Hai annotation system song song | Critical | — |
| A3 | Suggestion dùng pipeline kém | High | — |
| A4 | Review queue ẩn model predictions | High | A1 (partial) |
| A6 | BIO export tokenization sai | High | — |
| A5 | Entity ↔ LabelAnnotation tách biệt | High | A1 |
| U1 | Edit annotation thiếu trong LabelingPage | Medium | U2 |
| U2 | AnnotationView orphaned | Medium | — |
| A7 | Role system inconsistent | Medium | — |
| U3 | Bug offset AnnotationView | Low | — |

---

## Thứ tự làm đề xuất

```
Phase 1 — Sửa nhanh, không đụng schema  ✅ DONE (commit 02f6f77)
  U2  ✅ Kết nối AnnotationView vào navigation
  U1  ✅ Thêm edit mode vào LabelingPage
  A3  ✅ Suggestion endpoint dùng MedicalNERPipeline
  A7  ✅ Chuẩn hóa role constants (xóa labeler)
  U3  ✅ Fix focusNode check + trim bug

Phase 2 — Sửa data layer  ✅ DONE (commit pending)
  A6  ✅ Vietnamese tokenizer (underthesea) cho BIO export — feedback.py + data_preparation.py
  A4  ✅ Snapshot model predictions khi tạo LabelSubmission; review queue đọc từ đó
        + migration: a1b2c3d4e5f6_add_model_predictions_to_label_submissions.py
  A1  ❌ Unified annotation table — schema refactor lớn, dời sang sau

Phase 3 — Feedback loop
  A2  ❌ Implement feedback contract (dict expansion + training queue)
  A5  ❌ Reconcile Entity table với confirmed LabelAnnotation
```

---

*File này là tracking document — cập nhật khi từng item được fix.*
