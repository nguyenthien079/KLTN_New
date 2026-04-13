# 🏥 Vietnamese Medical NER System

Hệ thống nhận diện thực thể y tế tiếng Việt (Named Entity Recognition) sử dụng ensemble model với PhoBERT, Dictionary-based và Rule-based extractors.

## 📋 Mục Lục

- [Tổng Quan Hệ Thống](#-tổng-quan-hệ-thống)
- [Kiến Trúc](#-kiến-trúc)
- [Frontend](#-frontend)
- [Backend](#-backend)
- [Database](#-database)
- [ML Pipeline](#-ml-pipeline)
- [Workflow](#-workflow)
- [Setup & Installation](#-setup--installation)
- [Key Insights](#-key-insights)

---

## 🎯 Tổng Quan Hệ Thống

Hệ thống nhận diện 6 loại thực thể y tế từ văn bản tiếng Việt:
- **DISEASE** (Bệnh): viêm phổi, ung thư, tiểu đường...
- **DRUG** (Thuốc): paracetamol, amoxicillin, insulin...
- **SYMPTOM** (Triệu chứng): sốt cao, ho, đau đầu...
- **TREATMENT** (Điều trị): phẫu thuật, hóa trị, vật lý trị liệu...
- **BODY_PART** (Bộ phận cơ thể): phổi, tim, gan...
- **TEST** (Xét nghiệm): X-quang, CT scan, xét nghiệm máu...

---

## 🏗 Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                             │
│          React 18 + Vite + Axios                           │
│  - Input: Text/URL                                         │
│  - Display: Highlighted entities with confidence scores    │
└─────────────────┬───────────────────────────────────────────┘
                  │ HTTP/REST API
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND                              │
│              FastAPI + SQLAlchemy                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Routers    │  │   Pipeline   │  │   Crawler    │    │
│  │              │  │              │  │              │    │
│  │ /api/ner     │  │ Segmenter    │  │ Vinmec       │    │
│  │ /api/crawl   │  │ Normalizer   │  │ SKDS         │    │
│  │ /api/pipeline│  │ Deduplicator │  │              │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘    │
│         │                 │                                │
│         ▼                 ▼                                │
│  ┌─────────────────────────────────────────┐              │
│  │          ML ENSEMBLE PIPELINE           │              │
│  │                                         │              │
│  │  ┌─────────────┐  ┌──────────────┐    │              │
│  │  │  PhoBERT    │  │  Dictionary  │    │              │
│  │  │  Extractor  │  │  Extractor   │    │              │
│  │  │  (0.7 w)    │  │  (1.0 w)     │    │              │
│  │  └─────────────┘  └──────────────┘    │              │
│  │                                         │              │
│  │  ┌──────────────┐                      │              │
│  │  │  Rule-based  │                      │              │
│  │  │  Extractor   │                      │              │
│  │  │  (0.5 w)     │                      │              │
│  │  └──────────────┘                      │              │
│  │                                         │              │
│  │  → Weighted Voting → Entity Grouping   │              │
│  └─────────────────────────────────────────┘              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   DATABASE (PostgreSQL)                     │
│                                                             │
│  articles ─── sentences ─── entities ─── knowledge_maps    │
│     │            │                                          │
│     │            └── extracted entities with positions      │
│     └── crawled content + metadata                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Frontend

### Tech Stack
- **React 18**: UI framework
- **Vite**: Build tool (fast HMR)
- **Axios**: HTTP client
- **CSS3**: Styling with gradients & animations

### Cấu Trúc

```
frontend/
├── src/
│   ├── App.jsx              # Main component
│   ├── components/
│   │   ├── EntityTag.jsx    # Colored entity tags
│   │   └── HighlightedSentence.jsx  # Highlight entities in text
│   ├── services/
│   │   └── api.js           # API client (analyzeText, analyzeUrl)
│   ├── config/
│   │   └── entityColors.js  # Color mapping for entity types
│   └── styles/
│       └── index.css
└── package.json
```

### Key Components

#### 1. **App.jsx** - Main UI
```javascript
// State management
const [inputType, setInputType] = useState('text');  // 'text' or 'url'
const [results, setResults] = useState(null);

// Analysis flow
handleAnalyze() → analyzeText/analyzeUrl → display results
```

#### 2. **HighlightedSentence.jsx** - Entity Highlighting
```javascript
// Hiển thị câu với entities được highlight
// Sắp xếp entities theo vị trí start/end
// Render text + EntityTag components
```

#### 3. **api.js** - API Integration
```javascript
analyzeText(text) → POST /api/ner/analyze
analyzeUrl(url) → POST /api/ner/analyze-url
```

---

## ⚙️ Backend

### Tech Stack
- **FastAPI**: Modern async web framework
- **SQLAlchemy 2.0**: Async ORM
- **Pydantic**: Data validation
- **Uvicorn**: ASGI server
- **Alembic**: Database migrations

### Cấu Trúc

```
backend/
├── app/
│   ├── main.py              # FastAPI app + CORS + lifespan
│   ├── config.py            # Settings (DATABASE_URL, SECRET_KEY)
│   ├── database.py          # Async engine + session
│   │
│   ├── routers/             # API Endpoints
│   │   ├── ner.py           # /api/ner/* - NER analysis
│   │   ├── crawler.py       # /api/crawl/* - Web crawling
│   │   ├── pipeline.py      # /api/pipeline/* - Text processing
│   │   └── admin.py         # /api/admin/* - Stats & management
│   │
│   ├── models/              # Database Models (SQLAlchemy)
│   │   ├── article.py       # Article (crawled content)
│   │   ├── sentence.py      # Sentence (segmented text)
│   │   ├── entity.py        # Entity (extracted entities)
│   │   └── knowledge_map.py # KnowledgeMap (entity relationships)
│   │
│   ├── ml/                  # Machine Learning
│   │   ├── ensemble.py      # MedicalNERPipeline (main)
│   │   ├── extractors/
│   │   │   ├── base.py      # BaseExtractor, Entity dataclass
│   │   │   ├── phobert.py   # PhoBERT transformer
│   │   │   ├── dictionary.py # Dictionary matching
│   │   │   └── rule_based.py # Regex patterns
│   │   ├── trainer.py       # PhoBET fine-tuning
│   │   └── config.py        # Weights & hyperparameters
│   │
│   ├── pipeline/            # Text Processing
│   │   ├── segmenter.py     # Sentence segmentation (underthesea)
│   │   ├── normalizer.py    # Text normalization
│   │   └── deduplicator.py  # Entity deduplication
│   │
│   ├── crawler/             # Web Scraping
│   │   ├── crawler.py       # Generic crawler
│   │   ├── extractor.py     # Content extraction
│   │   └── sites/           # Site-specific crawlers
│   │       ├── vinmec.py
│   │       └── suckhoedoisong.py
│   │
│   └── utils/
│       ├── logger.py
│       └── metrics.py
│
├── data/
│   ├── dicts/               # Dictionary files
│   │   ├── diseases.txt     # ~1000 diseases
│   │   ├── drugs.txt        # ~800 drugs
│   │   ├── symptoms.txt
│   │   ├── treatments.txt
│   │   ├── body_parts.txt
│   │   └── tests.txt
│   └── training/            # Training data (JSON format)
│       ├── train.json
│       ├── val.json
│       └── test.json
│
└── requirements.txt
```

---

## 🗄 Database

### Schema

#### 1. **articles** - Bài báo đã crawl
```sql
- id              : Integer (PK)
- url             : String(2048) unique         -- URL đầy đủ trang đã crawl
- title           : String(512)
- source_domain   : String(255)                 -- hellobacsi.com, vinmec.com...
- raw_html        : Text                        -- HTML gốc (~457KB/bài, tổng ~540MB)
- clean_text      : Text                        -- Nội dung đã extract
- char_count      : Integer
- crawl_batch_id  : Integer
- crawled_at      : DateTime(timezone)
- status          : Enum(PENDING, IN_PROGRESS, COMPLETED, FAILED)
- content_hash    : String(64)                  -- SHA256 để deduplicate
- is_duplicate    : Boolean
- duplicate_of_id : Integer
- similarity_score: Float
```

#### 2. **sentences** - Câu được tách từ bài viết
```sql
- id              : Integer (PK)
- article_id      : Integer (FK → articles, CASCADE DELETE)
- raw_text        : Text                        -- Câu gốc
- normalized_text : Text                        -- Câu sau normalize
- char_count      : Integer
- word_count      : Integer
- pipeline_status : Enum(RAW, SEGMENTED, NORMALIZED, DEDUPLICATED, PROCESSED)
- is_medical      : Boolean
- medical_confidence: Float
- is_duplicate    : Boolean
- duplicate_of_id : Integer
- created_at      : DateTime(timezone)
- processed_at    : DateTime(timezone)
```

#### 3. **entities** - Thực thể y tế được trích xuất
```sql
- id              : Integer (PK)
- text            : String(512)                 -- Từ gốc: "viêm phổi"
- normalized_text : String(512)
- entity_type     : Enum(DISEASE, DRUG, SYMPTOM, TREATMENT, BODY_PART, TEST)
- frequency       : Integer
- avg_confidence  : Float
- first_seen      : DateTime(timezone)
- last_seen       : DateTime(timezone)
```

#### 4. **knowledge_map** - Liên kết entity ↔ sentence
```sql
- id              : Integer (PK)
- sentence_id     : Integer (FK → sentences, CASCADE DELETE)
- entity_id       : Integer (FK → entities, CASCADE DELETE)
- article_id      : Integer (FK → articles, CASCADE DELETE)
- start_pos       : Integer
- end_pos         : Integer
- confidence      : Float
- extractor       : String                      -- phobert / dictionary / rule_based
- created_at      : DateTime(timezone)
```

#### 5. **corrections** - Annotation thủ công (Human-in-the-Loop)
```sql
- id              : Integer (PK)
- ...
```

### Relationships
```
Article (1) ──→ (N) Sentence ──→ (N) KnowledgeMap ──→ (1) Entity
```

---

### 🔍 SELECT Queries Kiểm Tra Dữ Liệu

> **Lưu ý:** Tránh dùng `SELECT *` trên bảng `articles` vì cột `raw_html` rất nặng (~457KB/row).

#### Kết nối PostgreSQL

```bash
# Qua Docker
docker exec -it medical_ner_postgres psql -U medical_user -d medical_ner

# Qua psql trực tiếp
psql -h localhost -p 5432 -U medical_user -d medical_ner
```

#### Thống kê tổng quan

```sql
-- Đếm số bản ghi toàn bộ bảng
SELECT
  (SELECT COUNT(*) FROM articles)     AS total_articles,
  (SELECT COUNT(*) FROM sentences)    AS total_sentences,
  (SELECT COUNT(*) FROM entities)     AS total_entities,
  (SELECT COUNT(*) FROM knowledge_map) AS total_knowledge_maps,
  (SELECT COUNT(*) FROM corrections)  AS total_corrections;
```

```sql
-- Phân bổ theo nguồn crawl
SELECT source_domain,
       COUNT(*)            AS article_count,
       SUM(char_count)     AS total_chars,
       AVG(char_count)::int AS avg_chars
FROM articles
GROUP BY source_domain
ORDER BY article_count DESC;
```

```sql
-- Kích thước raw_html (vì sao không dùng SELECT *)
SELECT AVG(LENGTH(raw_html))::int AS avg_html_bytes,
       MAX(LENGTH(raw_html))::int AS max_html_bytes,
       (SUM(LENGTH(raw_html)) / 1024 / 1024)::int AS total_html_mb
FROM articles;
```

#### Kiểm tra bảng articles

```sql
-- Xem danh sách bài viết (không lấy raw_html, clean_text)
SELECT id, url, title, source_domain, char_count, status, crawled_at
FROM articles
ORDER BY id
LIMIT 50;
```

```sql
-- Tìm bài theo domain
SELECT id, url, title, char_count, status
FROM articles
WHERE source_domain = 'hellobacsi.com'
ORDER BY char_count DESC
LIMIT 20;
```

```sql
-- Kiểm tra URL đã crawl (tìm theo từ khóa)
SELECT id, url, title, crawled_at
FROM articles
WHERE url ILIKE '%benh-tieu-duong%'
   OR title ILIKE '%tiểu đường%';
```

```sql
-- Bài chưa xử lý pipeline
SELECT id, url, title, status
FROM articles
WHERE status != 'COMPLETED'
ORDER BY crawled_at DESC;
```

```sql
-- Kiểm tra duplicate
SELECT id, url, is_duplicate, duplicate_of_id, similarity_score
FROM articles
WHERE is_duplicate = true
LIMIT 20;
```

```sql
-- Xem nội dung text của một bài cụ thể (thay id)
SELECT id, url, title, clean_text
FROM articles
WHERE id = 1;
```

#### Kiểm tra bảng sentences

```sql
-- Số câu trung bình mỗi bài
SELECT AVG(cnt)::int AS avg_sentences_per_article,
       MAX(cnt)      AS max_sentences,
       MIN(cnt)      AS min_sentences
FROM (
  SELECT article_id, COUNT(*) AS cnt
  FROM sentences
  GROUP BY article_id
) sub;
```

```sql
-- Top 10 bài có nhiều câu nhất
SELECT a.id, a.url, a.title, COUNT(s.id) AS sentence_count
FROM articles a
JOIN sentences s ON s.article_id = a.id
GROUP BY a.id, a.url, a.title
ORDER BY sentence_count DESC
LIMIT 10;
```

```sql
-- Xem câu của một bài cụ thể (thay article_id)
SELECT id, raw_text, normalized_text, word_count, pipeline_status, is_medical
FROM sentences
WHERE article_id = 636
ORDER BY id;
```

```sql
-- Câu chứa từ khóa y tế
SELECT s.id, s.raw_text, s.word_count, a.url
FROM sentences s
JOIN articles a ON a.id = s.article_id
WHERE s.raw_text ILIKE '%ung thư%'
LIMIT 20;
```

```sql
-- Phân bổ pipeline_status
SELECT pipeline_status, COUNT(*) AS count
FROM sentences
GROUP BY pipeline_status;
```

#### Kiểm tra bảng entities

```sql
-- Tất cả entity types và số lượng
SELECT entity_type, COUNT(*) AS count
FROM entities
GROUP BY entity_type
ORDER BY count DESC;
```

```sql
-- Top entity xuất hiện nhiều nhất
SELECT text, normalized_text, entity_type, frequency, avg_confidence
FROM entities
ORDER BY frequency DESC
LIMIT 20;
```

```sql
-- Tìm entity theo loại
SELECT text, normalized_text, frequency
FROM entities
WHERE entity_type = 'DISEASE'
ORDER BY frequency DESC
LIMIT 20;
```

#### Join nhiều bảng

```sql
-- Câu + entity của một bài viết cụ thể (thay article_id)
SELECT
  s.id          AS sentence_id,
  s.raw_text,
  e.text        AS entity_text,
  e.entity_type,
  km.confidence,
  km.extractor
FROM sentences s
JOIN knowledge_map km ON km.sentence_id = s.id
JOIN entities e ON e.id = km.entity_id
WHERE s.article_id = 636
ORDER BY s.id, km.confidence DESC;
```

```sql
-- Toàn bộ pipeline: article → sentence → entity
SELECT
  a.url,
  a.title,
  a.source_domain,
  COUNT(DISTINCT s.id)  AS sentences,
  COUNT(DISTINCT km.id) AS entity_mentions
FROM articles a
LEFT JOIN sentences s  ON s.article_id = a.id
LEFT JOIN knowledge_map km ON km.article_id = a.id
GROUP BY a.id, a.url, a.title, a.source_domain
ORDER BY entity_mentions DESC
LIMIT 20;
```

---

## 🤖 ML Pipeline

### Ensemble Architecture

#### **MedicalNERPipeline** (`app/ml/ensemble.py`)

```python
class MedicalNERPipeline:
    """
    Ensemble pipeline kết hợp 3 extractors với weighted voting
    """
    
    def __init__(self, min_confidence=0.4):
        self.extractors = [
            PhoBERTExtractor(),      # weight: 0.7
            DictionaryExtractor(),   # weight: 1.0
            RuleBasedExtractor()     # weight: 0.5
        ]
    
    def extract(self, text: str) -> List[Entity]:
        # 1. Run all extractors
        all_entities = []
        for extractor in self.extractors:
            all_entities.extend(extractor.extract(text))
        
        # 2. Group overlapping entities (cùng type, vị trí gần nhau)
        grouped = self._group_entities(all_entities)
        
        # 3. Weighted voting cho mỗi group
        final_entities = []
        for group in grouped:
            weighted_conf = sum(
                e.confidence * WEIGHTS[e.source] 
                for e in group
            )
            final_conf = weighted_conf / sum(WEIGHTS.values())
            
            if final_conf >= self.min_confidence:
                final_entities.append(Entity(..., confidence=final_conf))
        
        return final_entities
```

### Extractors

#### 1. **PhoBERTExtractor** (`extractors/phobert.py`)
```python
"""
Transformer-based NER sử dụng PhoBERT fine-tuned
- Model: vinai/phobert-base
- Fine-tuned trên medical corpus
- Aggregation strategy: simple (merge subtokens)
"""

def extract(self, text: str) -> List[Entity]:
    results = self._pipeline(text)  # HuggingFace pipeline
    
    entities = []
    for result in results:
        start = result.get('start')
        end = result.get('end')
        
        # FIX: Handle None positions from transformer
        if start is None or end is None:
            start = text.lower().find(result['word'].lower())
            if start == -1:
                continue  # Skip nếu không tìm được
            end = start + len(result['word'])
        
        entities.append(Entity(
            text=result['word'],
            entity_type=result['entity_group'],
            start=start,
            end=end,
            confidence=result['score'],
            source='phobert'
        ))
    
    return entities
```

**Insight**: PhoBERT đôi khi trả về `None` cho `start/end` do tokenization issues → cần fallback tìm vị trí thủ công.

#### 2. **DictionaryExtractor** (`extractors/dictionary.py`)
```python
"""
Exact matching với từ điển y tế
- 6000+ terms từ data/dicts/
- Regex với word boundaries
- Longest match first (tránh match con)
"""

def extract(self, text: str) -> List[Entity]:
    entities = []
    text_lower = text.lower()
    
    for entity_type, terms in self.dictionaries.items():
        # Sort by length desc → match "viêm phổi cấp" trước "viêm phổi"
        for term in sorted(terms, key=len, reverse=True):
            pattern = r'\b' + re.escape(term) + r'\b'
            
            for match in re.finditer(pattern, text_lower):
                entities.append(Entity(
                    text=text[match.start():match.end()],
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,  # Exact match = high confidence
                    source='dictionary'
                ))
    
    return entities
```

**Insight**: Dictionary có confidence cao nhất (1.0) vì exact match, nhưng cần update thường xuyên.

#### 3. **RuleBasedExtractor** (`extractors/rule_based.py`)
```python
"""
Regex patterns cho Vietnamese medical entities
- Patterns như: r'\bviêm\s+\w+', r'\bbệnh\s+\w+'
- Flexible nhưng confidence thấp hơn
"""

patterns = {
    'DISEASE': [
        r'\bviêm\s+\w+',           # viêm phổi, viêm gan
        r'\bbệnh\s+\w+(?:\s+\w+)?', # bệnh tim, bệnh ung thư
        r'\b\w+\s+mãn tính',        # ... mãn tính
    ],
    'SYMPTOM': [
        r'\bđau\s+\w+',             # đau đầu, đau bụng
        r'\bsốt\s+(?:cao|nhẹ)?',    # sốt, sốt cao
    ],
    # ...
}
```

**Insight**: Rule-based bắt được patterns linh hoạt nhưng nhiễu cao → weight thấp nhất (0.5).

### Entity Grouping & Voting

```python
def _group_entities(self, entities: List[Entity]) -> List[List[Entity]]:
    """
    Group các entities cùng type và overlapping
    
    Example:
    - PhoBERT: "viêm phổi" (start=10, end=19, conf=0.85)
    - Dictionary: "viêm phổi" (start=10, end=19, conf=1.0)
    - Rule: "viêm phổi" (start=10, end=19, conf=0.7)
    
    → Group lại → Weighted avg = 0.7*0.85 + 1.0*1.0 + 0.5*0.7 = 0.89
    """
    
    groups = []
    for entity in entities:
        # Tìm group có entity cùng type và overlapping
        found = False
        for group in groups:
            if (entity.entity_type == group[0].entity_type and 
                self._is_overlapping(entity, group[0])):
                group.append(entity)
                found = True
                break
        
        if not found:
            groups.append([entity])
    
    return groups

def _is_overlapping(self, e1: Entity, e2: Entity) -> bool:
    """Check if 2 entities overlap"""
    if None in (e1.start, e1.end, e2.start, e2.end):
        return e1.normalized_text == e2.normalized_text
    
    return not (e1.end <= e2.start or e2.end <= e1.start)
```

---

## 🔄 Workflow

### 1. **Text Analysis Flow** (`/api/ner/analyze`)

```
User Input (text)
    ↓
Sentence Segmentation (underthesea)
    ↓
For each sentence:
    ↓
    MedicalNERPipeline.extract()
        ↓
        ┌─────────────────────────────────┐
        │  Run 3 extractors in parallel  │
        ├─────────────────────────────────┤
        │  1. PhoBERT → entities_1        │
        │  2. Dictionary → entities_2     │
        │  3. Rule-based → entities_3     │
        └─────────────────────────────────┘
        ↓
    Group overlapping entities
        ↓
    Weighted voting (apply weights)
        ↓
    Filter by min_confidence (0.4)
        ↓
    Return List[Entity]
    ↓
Response JSON:
{
    "sentences": [
        {
            "sentence": "...",
            "entities": [
                {
                    "text": "viêm phổi",
                    "type": "DISEASE",
                    "start": 10,
                    "end": 19,
                    "confidence": 0.89,
                    "source": "phobert+dictionary+rule_based"
                }
            ]
        }
    ],
    "stats": {
        "DISEASE": 2,
        "DRUG": 1,
        ...
    }
}
```

### 2. **URL Analysis Flow** (`/api/ner/analyze-url`)

```
User Input (URL)
    ↓
Crawler.fetch(url)
    ↓
Content Extraction
    ↓
Text Normalization
    ↓
[Same as Text Analysis Flow]
    ↓
Response + metadata (title, source, url)
```

### 3. **Batch Crawling Flow** (`/api/crawl/batch`)

```
Input: source_name + max_articles
    ↓
SiteCrawler (Vinmec/SKDS)
    ↓
For each URL:
    ↓
    Fetch HTML
    ↓
    Extract: title, content, metadata
    ↓
    Deduplication check (hash content)
    ↓
    Save to Article model
    ↓
    [Optional] Run NER pipeline
    ↓
    Save entities to database
    ↓
Return summary statistics
```

---

## 📊 Data Pipeline - Complete Workflow

### Overview: Từ Crawl → Training → Production

```
┌─────────────────────────────────────────────────────────────┐
│                    STEP 1: CRAWL DATA                       │
│          Crawl medical articles from websites               │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                STEP 2: PROCESS & FILTER                     │
│         Segment, normalize, filter quality                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 3: PREPARE TRAINING DATA                  │
│    Auto-label using Dictionary + Rule-based extractors     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 STEP 4: TRAIN PHOBERT                       │
│           Fine-tune PhoBERT on labeled data                 │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                STEP 5: EVALUATE & EXPORT                    │
│              Test model and export to production            │
└─────────────────────────────────────────────────────────────┘
```

---

### STEP 1: Crawl Medical Articles

#### 1.1 Single URL Crawl (Quick Test)

```bash
cd backend

# Crawl single article
python test_crawl.py

# Or use API
curl -X POST http://localhost:8000/api/crawl/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.vinmec.com/vie/benh/viem-phoi-1234"}'
```

#### 1.2 Batch Crawl (Production)

**Script**: `scripts/crawl_batch.py`

```bash
# Crawl from 5 medical websites
python scripts/crawl_batch.py

# Sites included:
# - Sức Khỏe Đời Sống: ~300 pages
# - Vinmec: ~300 pages
# - Hello Bacsi: ~200 pages
# - Bệnh Viện Tâm Anh: ~200 pages
# - Nhà Thuốc Long Châu: ~250 pages
# Total: ~1250 pages
```

**Configuration** (`crawl_batch.py`):
```python
SITES = [
    {
        "name": "Sức Khỏe Đời Sống",
        "urls": [
            "https://suckhoedoisong.vn/benh",
            "https://suckhoedoisong.vn/thuoc",
            "https://suckhoedoisong.vn/trieu-chung"
        ],
        "max_pages": 300
    },
    # ... more sites
]
```

**Output**:
- Articles saved to `articles` table
- Metadata: title, url, content, source, crawled_at
- Auto-deduplication by content hash

**Expected Time**: ~30-60 minutes (with delays to respect rate limits)

---

### STEP 2: Process & Filter Articles

#### 2.1 Run Pipeline (Segment + Normalize)

**Script**: `scripts/run_pipeline.py`

```bash
python scripts/run_pipeline.py

# Pipeline steps:
# 1. Sentence segmentation (underthesea)
# 2. Text normalization (lowercase, strip)
# 3. Deduplication (similar sentences)
# 4. Save to 'sentences' table
```

**What it does**:
```python
# For each article:
Article.content 
  → Segmenter.segment() 
  → ["Sentence 1", "Sentence 2", ...]
  → Normalizer.normalize()
  → Deduplicator.check()
  → Save to Sentence model
```

**Output**:
```
PIPELINE COMPLETED
==========================================
Articles processed: 1250
Total sentences:    45,000
==========================================
```

#### 2.2 Filter Quality

**Script**: `scripts/filter_quality.py`

```bash
python scripts/filter_quality.py

# Removes articles that:
# - Too short (< 200 chars)
# - Too long (> 50,000 chars)
# - Too few words (< 20 words)
# - Empty clean_text
```

**Quality Criteria**:
```python
VALID_ARTICLE = {
    'min_length': 200,
    'max_length': 50000,
    'min_words': 20,
    'has_clean_text': True
}
```

**Expected Result**:
- Remove ~10-15% low-quality articles
- Keep ~1100-1150 high-quality articles
- ~40,000 clean sentences

---

### STEP 3: Prepare Training Data

**Script**: `scripts/prepare_training_data.py`

```bash
python scripts/prepare_training_data.py

# Output:
# data/training/
#   ├── train.json (70%)
#   ├── val.json   (15%)
#   └── test.json  (15%)
```

#### How Auto-Labeling Works:

```python
# Uses Dictionary + Rule-based extractors to label entities
# Format: BIO tagging

Input:  "Bệnh nhân bị viêm phổi và sốt cao"
Output: [
  {"token": "Bệnh", "tag": "O"},
  {"token": "nhân", "tag": "O"},
  {"token": "bị", "tag": "O"},
  {"token": "viêm", "tag": "B-DISEASE"},
  {"token": "phổi", "tag": "I-DISEASE"},
  {"token": "và", "tag": "O"},
  {"token": "sốt", "tag": "B-SYMPTOM"},
  {"token": "cao", "tag": "I-SYMPTOM"}
]
```

**Data Preparation Flow**:
```python
# 1. Load sentences from database
SELECT * FROM sentences 
WHERE is_medical = True 
AND is_duplicate = False

# 2. Apply Dictionary + Rule extractors
DataPreparator.create_dataset(sentences)

# 3. Convert to BIO format
# 4. Split: 70% train / 15% val / 15% test
# 5. Save as JSON
```

**Expected Output**:
```
Loaded 40,000 sentences from database
Created 35,000 labeled samples (good entity coverage)
Train: 24,500, Val: 5,250, Test: 5,250
Training data saved to data/training/
```

**Sample JSON Format**:
```json
{
  "id": "sent-001",
  "tokens": ["Bệnh", "nhân", "bị", "viêm", "phổi"],
  "tags": ["O", "O", "O", "B-DISEASE", "I-DISEASE"],
  "text": "Bệnh nhân bị viêm phổi"
}
```

---

### STEP 4: Train PhoBERT

**Script**: `scripts/train_phobert.py`

```bash
python scripts/train_phobert.py

# Training parameters:
# - Base model: vinai/phobert-base
# - Learning rate: 2e-5
# - Batch size: 16
# - Epochs: 5
# - Output: models/phobert-medical/
```

#### Training Configuration:

```python
trainer = PhoBERTNERTrainer(
    model_name="vinai/phobert-base"  # Vietnamese BERT
)

trainer.train(
    train_dataset=train_dataset,     # 24,500 samples
    val_dataset=val_dataset,         # 5,250 samples
    output_dir="models/phobert-medical",
    num_epochs=5,
    learning_rate=2e-5,
    batch_size=16,
    warmup_steps=500,
    weight_decay=0.01,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True
)
```

#### Training Output:

```
Epoch 1/5
==========
Train Loss: 0.245 | Val Loss: 0.198 | F1: 0.72
Saving checkpoint...

Epoch 2/5
==========
Train Loss: 0.156 | Val Loss: 0.143 | F1: 0.78
Saving checkpoint...

...

Epoch 5/5
==========
Train Loss: 0.089 | Val Loss: 0.102 | F1: 0.85
✓ Best model saved!

Training completed!
Model saved to: models/phobert-medical/final_model/
```

**Expected Time**: 2-4 hours (GPU) / 12-24 hours (CPU)

**Model Output**:
```
models/phobert-medical/
├── final_model/
│   ├── config.json
│   ├── pytorch_model.bin
│   ├── tokenizer_config.json
│   ├── vocab.txt
│   └── special_tokens_map.json
├── checkpoint-epoch-1/
├── checkpoint-epoch-2/
└── training_logs.json
```

---

### STEP 5: Evaluate & Export

#### 5.1 Evaluate Model

**Script**: `scripts/evaluate_model.py`

```bash
python scripts/evaluate_model.py \
  --model-path models/phobert-medical/final_model \
  --test-data data/training/test.json

# Output:
# ==========================================
# EVALUATION RESULTS
# ==========================================
# 
# Overall Metrics:
#   Precision: 0.86
#   Recall:    0.84
#   F1 Score:  0.85
# 
# Per-Entity Metrics:
#   DISEASE:    P=0.88  R=0.86  F1=0.87
#   DRUG:       P=0.91  R=0.89  F1=0.90
#   SYMPTOM:    P=0.82  R=0.80  F1=0.81
#   TREATMENT:  P=0.85  R=0.83  F1=0.84
#   BODY_PART:  P=0.87  R=0.85  F1=0.86
#   TEST:       P=0.89  R=0.86  F1=0.87
# ==========================================
```

#### 5.2 Export Model

**Script**: `scripts/export_model.py`

```bash
python scripts/export_model.py \
  --input models/phobert-medical/final_model \
  --output models/phobert-medical-production

# Creates production-ready model package
```

#### 5.3 Update Production

```bash
# Copy trained model to production path
cp -r models/phobert-medical/final_model models/phobert-medical/

# Restart API server
uvicorn app.main:app --reload --port 8000

# Test ensemble with new model
curl -X POST http://localhost:8000/api/ner/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Bệnh nhân bị viêm phổi, điều trị bằng amoxicillin"}'
```

---

### Complete Pipeline Command Sequence

```bash
# ========================================
# FULL PIPELINE - Run in order
# ========================================

cd backend

# 1. Crawl data (~30-60 min)
python scripts/crawl_batch.py

# 2. Process articles (~5-10 min)
python scripts/run_pipeline.py

# 3. Filter quality (~1 min)
python scripts/filter_quality.py

# 4. Prepare training data (~2-5 min)
python scripts/prepare_training_data.py

# 5. Train PhoBERT (~2-4 hours GPU / 12-24 hours CPU)
python scripts/train_phobert.py

# 6. Evaluate model (~5 min)
python scripts/evaluate_model.py

# 7. Export to production (~1 min)
python scripts/export_model.py

# ========================================
# Total time: ~3-5 hours (with GPU)
# ========================================
```

---

### Data Statistics (After Pipeline)

```
Raw Articles (crawled):      ~1,250
After Quality Filter:        ~1,100
Total Sentences:             ~40,000
Labeled Samples:             ~35,000
  ├── Train:                 24,500 (70%)
  ├── Validation:            5,250  (15%)
  └── Test:                  5,250  (15%)

Entity Distribution:
  ├── DISEASE:               ~12,000
  ├── SYMPTOM:               ~8,500
  ├── DRUG:                  ~7,000
  ├── TREATMENT:             ~4,500
  ├── BODY_PART:             ~2,500
  └── TEST:                  ~2,000
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp ../.env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY

# Run base migrations (articles, sentences, entities, knowledge_map, corrections)
alembic upgrade head

# [NEW] Migrate: tạo bảng users + thêm cột auth vào corrections
python scripts/migrate_add_auth_columns.py

# [NEW] Migrate: tạo các bảng cho hệ thống labeling & phân quyền
#   - role_requests
#   - label_assignments
#   - label_submissions
#   - label_annotations
python scripts/migrate_labeling_tables.py

# [NEW] Seed tài khoản admin mặc định (admin / admin123)
python scripts/seed_admin.py

# Download PhoBERT model (optional)
# Place in: models/phobert-medical/final_model/

# Run server
uvicorn app.main:app --reload --port 8000
```

> **Lưu ý thứ tự:** Phải chạy `migrate_add_auth_columns.py` trước `migrate_labeling_tables.py` vì bảng `users` cần tồn tại trước.

### Roles trong hệ thống

| Role | Quyền |
|------|-------|
| `admin` | Toàn quyền: quản lý user, assign bài, xem tất cả submission, export |
| `chuyen_gia` | Assign bài, xem tất cả submission, hoàn thành review + export CSV/JSON |
| `labeler` | Gán nhãn các bài được assign, nộp submission |

Sau khi seed admin, đăng nhập bằng `admin / admin123` và tạo thêm tài khoản labeler/chuyên gia qua trang Users.

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev  # Port 5173
```

### Docker Setup

```bash
# From project root
docker-compose up -d

# Services:
# - backend: localhost:8000
# - frontend: localhost:3000
# - postgres: localhost:5432
```

---

## 💡 Key Insights

### 1. **Ensemble > Single Model**
- PhoBERT alone: ~78% F1
- Dictionary alone: ~65% F1 (high precision, low recall)
- **Ensemble**: ~85% F1 (balanced precision & recall)

### 2. **Position Handling is Critical**
```python
# PhoBERT transformers pipeline sometimes returns None for start/end
# Must implement fallback position detection
if start is None:
    start = text.lower().find(word.lower())
```

### 3. **Vietnamese Segmentation Matters**
```python
# Bad: "Bệnhnhânbịviêmphổi" (no spaces)
# Good: "Bệnh nhân bị viêm phổi"
# Use underthesea.sent_tokenize() before NER
```

### 4. **Confidence Calibration**
```python
ENSEMBLE_WEIGHTS = {
    'phobert': 0.7,      # Good but can hallucinate
    'dictionary': 1.0,   # Exact match → highest trust
    'rule_based': 0.5    # Flexible but noisy → lower trust
}
```

### 5. **Longest Match First**
```python
# Dictionary matching: sort by length DESC
# Prevents: "viêm" + "phổi" instead of "viêm phổi"
for term in sorted(terms, key=len, reverse=True):
    # match logic
```

### 6. **Async All The Way**
```python
# FastAPI + async SQLAlchemy = high concurrency
# But ML inference = CPU-bound → use ThreadPoolExecutor
_executor = ThreadPoolExecutor(max_workers=2)
entities = await loop.run_in_executor(_executor, pipeline.extract, text)
```

### 7. **Database Normalization**
```
# Store both original & normalized text
text: "VIÊM PHỔI"
normalized_text: "viêm phổi"  # For deduplication & search
```

### 8. **CORS Configuration**
```python
# Development: allow localhost:5173 (Vite)
# Production: whitelist specific domains
ALLOWED_ORIGINS = ["http://localhost:5173", "https://your-domain.com"]
```

---

## 📊 Performance

- **Latency**: ~200-500ms per sentence (depending on model availability)
- **Throughput**: ~10-20 requests/second (single worker)
- **Accuracy**: F1 ~0.85 on medical corpus

---

## 🔧 Development

### Running Tests
```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Training PhoBERT
```bash
cd backend
python scripts/train_phobert.py --epochs 10 --lr 2e-5
```

### Evaluating Model
```bash
python scripts/evaluate_model.py --model-path models/phobert-medical
```

---

## 📝 License

MIT License

---

## 👥 Contributors

- **Nguyen Thien** ([@nguyenthien079](https://github.com/nguyenthien079))
  - Backend: FastAPI + ML Pipeline
  - Frontend: React UI
  - ML: PhoBERT fine-tuning & Ensemble

---

**Built with ❤️ for Vietnamese Healthcare NLP**
