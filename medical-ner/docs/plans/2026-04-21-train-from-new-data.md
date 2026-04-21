# Plan: Train PhoBERT NER from New Labeled Data

**Date:** 2026-04-21 (corrected after strict review)  
**Data source:** `d:/Dev/Thanh/new/data/` — 328 files JSON đã có entity labels  
**Target:** Fine-tune PhoBERT NER sử dụng data mới, giữ traceability về source

> **Scope:** Chỉ dùng data từ `new/data/*.json`. Data cũ (từ DB qua `prepare_training_data.py` + dictionary matching) **không được dùng** — data đó không đúng. Script mới thay thế hoàn toàn, overwrite `data/training/`.

---

## Strict Review — Assumption Audit

### Assumption Audit Table

| # | Claim từ plan cũ | Status | Bằng chứng |
|---|---|---|---|
| 1 | Format JSON: `{filename, text, entities: [{text, label, start, end}]}` | ✅ VERIFIED | Đọc trực tiếp file |
| 2 | 328 disease topics (326 base, 1 timestamped, 1 cả hai) | ✅ VERIFIED | Script count output |
| 3 | Char-span chính xác: `text[start:end] == entity.text` | ✅ VERIFIED | 0/69 mismatches trên alzheimer.json |
| 4 | `trainer.py` LABELS: 13 labels, hardcoded | ✅ VERIFIED | Lines 21-29 |
| 5 | `load_dataset()` đọc `tokens` và `tags` keys | ✅ VERIFIED | Lines 63-64 |
| 6 | `config.py` BIO_LABELS → được dùng bởi `trainer.py` | ❌ INCORRECT | `trainer.py` KHÔNG import `config.py`. Chỉ `ensemble.py` import. Hai file HOÀN TOÀN ĐỘC LẬP |
| 7 | HuggingFace Trainer tự bỏ qua cột không phải input/label | ✅ VERIFIED | `remove_unused_columns=True` là default. Không set trong code → dùng default |
| 8 | Plan không đề cập sentence splitting | ❌ MISSING | Article có 801 word-tokens, max_length=256. Cần split câu TRƯỚC KHI convert BIO |
| 9 | `underthesea.sent_tokenize` có sẵn | ✅ VERIFIED | Import thành công, 40 sentences từ alzheimer |
| 10 | Entity spans không cross sentence boundaries | ✅ VERIFIED | 0/324 cross-boundary trong 7 files test |
| 11 | `DataPreparator._char_to_token_indices` dùng được cho data mới | ⚠️ ASSUMED | Logic đúng nhưng có edge case: compound token "hội chứng Alzheimer" bao trùm entity "Alzheimer" → cả compound token bị tag B-DISEASE. Acceptable nhưng cần ghi chú |
| 12 | `tokenize_and_align_labels` propagate B-/I- đúng chuẩn | ❌ INCORRECT | Lines 108-111: CẢ HAI NHÁNH `if/else` đều làm `self.label2id[label[word_idx]]` — subword thứ 2 trở đi nhận cùng tag với subword đầu (B→B thay vì B→I). Pre-existing bug, không phải lỗi mới, nhưng phải biết |

---

## Critical Issues Found

### Issue 1 — CRITICAL: config.py và trainer.py là hai hệ thống TÁCH RỜI
**File:** `trainer.py` line 21-29, `config.py` hoàn toàn

`PhoBERTNERTrainer.LABELS` là **class variable hardcoded** trong `trainer.py`. `config.py`'s `BIO_LABELS` **không được import** vào trainer. Nếu plan chỉ sửa `config.py` mà quên sửa `trainer.py`, training KHÔNG thay đổi gì cả.

**Breakpoint:** Nếu converter tạo samples với tag `"B-VALUE"` nhưng `trainer.LABELS` chưa có `"B-VALUE"`:
```python
# Line 109 trainer.py
label_ids.append(self.label2id[label[word_idx]])
# → KeyError: 'B-VALUE' khi gặp sample từ data mới
```
Training crash ngay lập tức.

### Issue 2 — CRITICAL: Article-level text vượt quá max_length=256

**Bằng chứng từ test:**
```
alzheimer.json: 801 word-tokens (underthesea)
max_length: 256 subword tokens
Ratio: 3.1x over limit
```

`trainer.py` dùng `truncation=True` → tự cắt bỏ phần > 256 token. Với article 801 tokens, **~68% data bị mất** hoàn toàn. Thêm nữa, các entities nằm ở nửa sau bài viết sẽ KHÔNG được train.

**Giải pháp bắt buộc:** Split article → sentences trước khi convert BIO. `underthesea.sent_tokenize` có sẵn, cho 40 sentences từ 1 article alzheimer. Entity spans hoàn toàn nằm trong sentence boundaries (0% cross-boundary từ test).

### Issue 3 — PRE-EXISTING BUG (biết để không blame plan mới)
**File:** `trainer.py` lines 108-111

```python
elif word_idx != previous_word_idx:
    label_ids.append(self.label2id[label[word_idx]])  # first subword: B-DISEASE
else:
    label_ids.append(self.label2id[label[word_idx]])  # same! should be I-DISEASE
```

Subword thứ 2, 3... của cùng 1 từ đều nhận tag giống subword đầu. Đây là bug có sẵn trong codebase, không phải lỗi plan mới tạo ra. Plan không cần fix bug này, nhưng cần biết để không gây confuse khi debug F1.

---

## Corrected Plan

### Bước 1 — Mở rộng LABELS trong `trainer.py` (KHÔNG phải chỉ config.py)

**File duy nhất cần sửa:** `backend/app/ml/trainer.py`

```python
# trainer.py line 21-29 — sửa class variable này
LABELS = [
    'O',
    'B-DISEASE', 'I-DISEASE',
    'B-DRUG', 'I-DRUG',
    'B-SYMPTOM', 'I-SYMPTOM',
    'B-TREATMENT', 'I-TREATMENT',
    'B-BODY_PART', 'I-BODY_PART',
    'B-TEST', 'I-TEST',
    'B-VALUE', 'I-VALUE',   # ← thêm mới
    'B-DATE', 'I-DATE',     # ← thêm mới
]
```

**Cũng sửa `config.py`** cho đồng bộ (dù không ảnh hưởng training):
```python
# config.py — cũng update BIO_LABELS và ENTITY_TYPES cho nhất quán
ENTITY_TYPES = {
    ...  # thêm 'VALUE': 'Chỉ số/giá trị', 'DATE': 'Thời gian'
}
BIO_LABELS = [..., 'B-VALUE', 'I-VALUE', 'B-DATE', 'I-DATE']
```

**Kiểm tra ngay sau bước này:**
```python
trainer = PhoBERTNERTrainer()
assert 'B-VALUE' in trainer.label2id, "B-VALUE missing from label2id"
assert 'B-DATE' in trainer.label2id, "B-DATE missing from label2id"
print(f"Total labels: {trainer.num_labels}")  # phải = 17
```

---

### Bước 2 — Viết script converter `import_from_new_data.py`

**Pipeline trong script:**

```
new/data/*.json
    ↓ deduplicate (prefer timestamped alzheimer)
    ↓ per article:
        ↓ sent_tokenize(text)  ← QUAN TRỌNG: split thành sentences
        ↓ per sentence:
            ↓ tìm entities thuộc sentence này (bằng char offset)
            ↓ adjust entity spans về local sentence offset  
            ↓ word_tokenize(sentence)
            ↓ char_span → BIO tags
            ↓ emit sample {source, tokens, tags}
    ↓ group by disease slug → split 80/10/10
    ↓ save train.json, val.json, test.json
```

**Deduplication:** Với alzheimer (duy nhất có cả 2 version), dùng timestamped (`alzheimer_20260415_145546.json`). Tất cả 326 file còn lại dùng base.

**Label mapping (áp dụng trước khi convert BIO):**

```python
LABEL_MAP = {
    'DISEASE':   'DISEASE',
    'SYMPTOM':   'SYMPTOM',
    'BODY_PART': 'BODY_PART',
    'TREATMENT': 'TREATMENT',
    'TEST':      'TEST',
    'MEDICATION':'DRUG',       # đổi tên
    'SUBSTANCE': 'DRUG',       # gộp vào DRUG
    'VALUE':     'VALUE',      # giữ nguyên, trainer đã có
    'DATE':      'DATE',       # giữ nguyên, trainer đã có
    # Bỏ hoàn toàn (không phải y tế):
    'DOCTOR':   None,
    'PATIENT':  None,
    'LOCATION': None,
    'Không có': None,
    'Không có thực thể y tế cụ thể, bỏ qua': None,
}
```

**Char-span → BIO** (tái dùng logic từ `data_preparation._char_to_token_indices`):

```python
def span_to_bio(text: str, entities: list[dict], label_map: dict) -> tuple[list, list]:
    """Convert char-span entities to BIO-tagged word tokens."""
    from underthesea import word_tokenize
    
    raw_tokens = word_tokenize(text)
    tokens = [t.replace('_', ' ') for t in raw_tokens]
    tags = ['O'] * len(tokens)
    
    # Sort by length desc để longest match wins khi overlap
    valid_entities = [
        e for e in entities
        if label_map.get(e['label']) is not None
    ]
    valid_entities.sort(key=lambda e: e['end'] - e['start'], reverse=True)
    
    for entity in valid_entities:
        mapped_label = label_map[entity['label']]
        start_tok, end_tok = char_to_token_indices(text, tokens, entity['start'], entity['end'])
        if start_tok is not None and end_tok is not None:
            # Only tag if not already tagged (longest match wins)
            if tags[start_tok] == 'O':
                tags[start_tok] = f'B-{mapped_label}'
                for i in range(start_tok + 1, end_tok + 1):
                    tags[i] = f'I-{mapped_label}'
    
    return tokens, tags
```

**Sentence-level splitting và entity projection:**

```python
def split_article_to_samples(text: str, entities: list, source: str, label_map: dict) -> list:
    from underthesea import sent_tokenize
    
    sentences = sent_tokenize(text)
    
    # Build sentence char offsets
    sent_ranges = []
    pos = 0
    for sent in sentences:
        start = text.find(sent, pos)
        if start == -1:
            continue
        sent_ranges.append((start, start + len(sent), sent))
        pos = start + len(sent)
    
    samples = []
    for s_start, s_end, sent_text in sent_ranges:
        # Find entities trong sentence này
        sent_entities = []
        for e in entities:
            if s_start <= e['start'] and e['end'] <= s_end:
                sent_entities.append({
                    'text': e['text'],
                    'label': e['label'],
                    'start': e['start'] - s_start,  # local offset
                    'end': e['end'] - s_start,
                })
        
        tokens, tags = span_to_bio(sent_text, sent_entities, label_map)
        
        # Skip sentences with no entities
        if all(t == 'O' for t in tags):
            continue
        
        samples.append({
            'source': source,
            'text': sent_text,
            'tokens': tokens,
            'tags': tags,
        })
    
    return samples
```

**Train/val/test split theo slug** (không phải per sentence):

```python
# Shuffle slugs, split 80/10/10
# Tất cả samples từ cùng 1 slug → cùng 1 split
# Tránh data leakage
```

---

### Bước 3 — Cập nhật `trainer.py` để giữ `source`

**File:** `backend/app/ml/trainer.py`

```python
def load_dataset(self, data_path: Path) -> Dataset:
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return Dataset.from_dict({
        "tokens": [item["tokens"] for item in data],
        "tags":   [item["tags"]   for item in data],
        "source": [item.get("source", "") for item in data],  # ← thêm
    })
```

`Trainer` sẽ tự bỏ cột `source` khi feed vào model (default `remove_unused_columns=True`). `source` được dùng sau training cho `evaluate_by_source.py`.

---

### Bước 4 — Script `train_from_new_data.py`

```bash
cd backend
python scripts/train_from_new_data.py \
  --data-dir ../../new/data \
  --output-dir models/phobert-medical \
  [--dry-run]   # chỉ convert + print stats, không train
```

Pipeline end-to-end:
```
import_from_new_data (convert + sentence-split)
    → data/training/train.json, val.json, test.json
trainer.load_dataset()
    → Dataset với tokens, tags, source
train_phobert (fine-tune)
    → models/phobert-medical/final_model/
```

---

### Bước 5 — Script `evaluate_by_source.py`

Load `test.json` → inference → group by `source` → print F1/Precision/Recall per disease slug.

---

## Verification Checklist (Bắt buộc chạy trước khi train)

```python
# Chạy sau bước 1:
trainer = PhoBERTNERTrainer()
assert trainer.num_labels == 17, f"Expected 17, got {trainer.num_labels}"
assert 'B-VALUE' in trainer.label2id
assert 'B-DATE' in trainer.label2id

# Chạy sau bước 2 (dry-run mode):
data = json.load(open('data/training/train.json'))
print(f"Train samples: {len(data)}")  # mong đợi 5000-15000

# Check label distribution
from collections import Counter
all_tags = [t for s in data for t in s['tags']]
dist = Counter(all_tags)
print("Label distribution:", dict(dist.most_common()))
# Đảm bảo không có label ngoài LABELS list

# Check source present
assert all('source' in s for s in data), "source field missing"
sources = set(s['source'] for s in data)
print(f"Unique sources in train: {len(sources)}")  # ~260-280 slugs

# Check không có unknown label
from app.ml.trainer import PhoBERTNERTrainer
trainer = PhoBERTNERTrainer()
unknown = set()
for s in data:
    for t in s['tags']:
        if t not in trainer.label2id:
            unknown.add(t)
assert len(unknown) == 0, f"Unknown labels found: {unknown}"

# Chạy 1 batch forward pass để verify không crash:
ds = trainer.load_dataset(Path('data/training/train.json'))
small = ds.select(range(min(4, len(ds))))
tokenized = small.map(trainer.tokenize_and_align_labels, batched=True)
print("First sample token count:", len(tokenized[0]['input_ids']))  # = 256
print("Labels sample:", tokenized[0]['labels'][:20])  # should have -100 and label IDs
```

---

## Thứ tự thực hiện (cập nhật)

```
Bước 1: Sửa trainer.py (LABELS), cũng sửa config.py    [~15 min]
         → verify: num_labels == 17, no KeyError
Bước 2: Viết import_from_new_data.py                    [~2h]
         (include sentence splitting, entity projection)
         → dry-run: verify label distribution, source field, no unknown tags
Bước 3: Cập nhật load_dataset() trong trainer.py        [~10 min]
Bước 4: Viết train_from_new_data.py                     [~30 min]
         → chạy full pipeline
Bước 5: Viết evaluate_by_source.py                      [~30 min]
```

---

## Lưu ý kỹ thuật (cập nhật)

### config.py và trainer.py độc lập
`trainer.py` **không** import `config.py`. Khi thêm label mới, phải sửa **cả hai** riêng lẻ. Đây là technical debt trong codebase hiện tại.

### Sentence splitting là bắt buộc
Article text ~800 word-tokens >> max_length=256. Nếu không split, 68% data bị cắt bỏ qua `truncation=True`. Dùng `underthesea.sent_tokenize` (đã verified available).

### Entity spans không cross sentence boundaries
Verified trên 7 files × 324 entities: 0 cross-boundary. An toàn để dùng sent_tokenize.

### Compound token behavior
`underthesea` gom "hội chứng Alzheimer" thành 1 token. Entity "Alzheimer" (sub-span) sẽ tag cả compound token là B-DISEASE. Đây là accepted behavior — kết quả inference sẽ trả về "hội chứng Alzheimer" thay vì chỉ "Alzheimer" khi dùng model. 

### Pre-existing subword tag bug
Lines 108-111 của `trainer.py`: subword tokens thứ 2+ nhận cùng tag với subword 1 (B→B thay vì B→I). Không fix trong scope này nhưng biết để không nhầm khi debug.
