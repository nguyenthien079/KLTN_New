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

#### 1. **articles** - Nội dung crawl được
```sql
- id: UUID (PK)
- url: String (unique)
- title: String
- content: Text
- source: String (vinmec, skds...)
- crawled_at: DateTime
- processed: Boolean
- quality_score: Float (0-1)
```

#### 2. **sentences** - Câu được segment
```sql
- id: UUID (PK)
- article_id: UUID (FK → articles)
- text: Text
- position: Integer (vị trí câu trong bài)
- created_at: DateTime
```

#### 3. **entities** - Thực thể được trích xuất
```sql
- id: UUID (PK)
- sentence_id: UUID (FK → sentences)
- text: String (từ gốc: "viêm phổi")
- normalized_text: String (chuẩn hóa: "viêm phổi")
- entity_type: Enum (DISEASE, DRUG, SYMPTOM...)
- start_pos: Integer (vị trí bắt đầu trong câu)
- end_pos: Integer (vị trí kết thúc)
- confidence: Float (0-1)
- source: String (phobert, dictionary, rule_based)
- created_at: DateTime
```

#### 4. **knowledge_maps** - Liên kết thực thể
```sql
- id: UUID (PK)
- entity1_id: UUID (FK → entities)
- entity2_id: UUID (FK → entities)
- relation_type: String (causes, treats, diagnoses...)
- confidence: Float
- created_at: DateTime
```

### Relationships
```
Article (1) ──→ (N) Sentence ──→ (N) Entity
                                      ↓
                            (N) ←── KnowledgeMap ──→ (N)
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

# Run migrations
alembic upgrade head

# Download PhoBERT model (optional)
# Place in: models/phobert-medical/final_model/

# Run server
uvicorn app.main:app --reload --port 8000
```

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

- **Backend**: FastAPI + ML Pipeline
- **Frontend**: React UI
- **ML**: PhoBERT fine-tuning & Ensemble

---

**Built with ❤️ for Vietnamese Healthcare NLP**
