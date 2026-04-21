# Crawl Page + Deploy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Thêm trang Crawl vào frontend (real-time progress + logs) và script deploy lên VPS Linux qua SSH + PEM key.

**Architecture:** Backend thêm `on_progress` callback vào `crawl_site()` để cập nhật `pages_crawled` và `logs[]` trong job dict trong lúc crawl đang chạy. Frontend thêm tab "Crawl" trong App.jsx, render `CrawlPage` component — poll `/api/crawl/status/{job_id}` mỗi 2 giây để hiển thị progress bar + terminal log. Deploy qua `deploy.sh` script (Git Bash/WSL trên Windows) dùng `ssh -i key.pem`.

**Tech Stack:** FastAPI (BackgroundTasks), React 18, Axios, CSS variables đã có, Docker Compose, OpenSSH

---

## Task 1: Backend — Real-time progress trong crawl job

**Files:**
- Modify: `backend/app/crawler/crawler.py` — thêm `on_progress` callback
- Modify: `backend/app/routers/crawler.py` — dùng callback + thêm `logs` vào job

### Step 1: Thêm `on_progress` vào `crawl_site()`

Trong `backend/app/crawler/crawler.py`, sửa signature của `crawl_site`:

```python
async def crawl_site(
    self,
    start_url: str,
    max_pages: int = 100,
    on_progress=None          # <-- thêm dòng này
) -> List[Article]:
```

Ngay sau dòng `crawled.append(article_data)`, thêm:

```python
            crawled.append(article_data)
            if on_progress:
                on_progress(len(crawled), url, extracted.get("title", ""))
            print(f"  [{len(crawled):>3}/{max_pages}] ...")
```

### Step 2: Cập nhật `run_crawl_job` trong router

Trong `backend/app/routers/crawler.py`, thêm `logs` vào job dict khi khởi tạo:

```python
crawl_jobs[job_id] = {
    "status": "running",
    "url": request.url,
    "pages_crawled": 0,
    "max_pages": request.max_pages,
    "logs": []          # <-- thêm dòng này
}
```

Trong `run_crawl_job`, thêm callback trước khi gọi `crawl_site`:

```python
async def run_crawl_job(job_id: str, url: str, max_pages: int):
    from app.database import AsyncSessionLocal
    from app.crawler.crawler import MedicalCrawler

    try:
        async with AsyncSessionLocal() as db:
            crawler = MedicalCrawler(db)

            def progress_callback(count: int, page_url: str, title: str):
                crawl_jobs[job_id]["pages_crawled"] = count
                label = title.strip()[:70] if title.strip() else page_url
                crawl_jobs[job_id]["logs"].append(
                    f"[{count}/{max_pages}] {label}"
                )

            articles = await crawler.crawl_site(
                url, max_pages=max_pages, on_progress=progress_callback
            )

            crawl_jobs[job_id]["status"] = "completed"
            crawl_jobs[job_id]["pages_crawled"] = len(articles)

    except Exception as e:
        crawl_jobs[job_id]["status"] = "failed"
        crawl_jobs[job_id]["error"] = str(e)
```

### Step 3: Cập nhật `CrawlStatusResponse` để trả về logs

Thêm `logs` vào Pydantic model và response:

```python
class CrawlStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: dict
    logs: list = []
```

Trong `get_crawl_status`:
```python
return CrawlStatusResponse(
    job_id=job_id,
    status=job["status"],
    progress={
        "pages_crawled": job.get("pages_crawled", 0),
        "max_pages": job.get("max_pages", 0)
    },
    logs=job.get("logs", [])
)
```

### Step 4: Commit

```bash
git add backend/app/crawler/crawler.py backend/app/routers/crawler.py
git commit -m "feat: add real-time progress callback to crawl job"
```

---

## Task 2: Frontend — CrawlPage component

**Files:**
- Create: `frontend/src/components/CrawlPage.jsx`
- Create: `frontend/src/components/CrawlPage.css`

### Step 1: Tạo `CrawlPage.jsx`

```jsx
// frontend/src/components/CrawlPage.jsx
import React, { useState, useEffect, useRef } from 'react';
import { startCrawl, getCrawlStatus } from '../services/api';
import './CrawlPage.css';

export default function CrawlPage() {
  const [url, setUrl] = useState('');
  const [maxPages, setMaxPages] = useState(100);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // null | 'running' | 'completed' | 'failed'
  const [progress, setProgress] = useState({ pages_crawled: 0, max_pages: 0 });
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const logRef = useRef(null);
  const pollRef = useRef(null);

  // Auto-scroll log terminal
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Polling
  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') return;

    pollRef.current = setInterval(async () => {
      try {
        const data = await getCrawlStatus(jobId);
        setStatus(data.status);
        setProgress(data.progress);
        setLogs(data.logs || []);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current);
        }
      } catch {
        clearInterval(pollRef.current);
      }
    }, 2000);

    return () => clearInterval(pollRef.current);
  }, [jobId, status]);

  const handleStart = async () => {
    if (!url.trim()) {
      setError('Vui lòng nhập URL.');
      return;
    }
    setError(null);
    setLogs([]);
    setProgress({ pages_crawled: 0, max_pages: maxPages });
    setStatus('running');
    try {
      const data = await startCrawl(url.trim(), maxPages);
      setJobId(data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu crawl.');
    }
  };

  const percent =
    progress.max_pages > 0
      ? Math.round((progress.pages_crawled / progress.max_pages) * 100)
      : 0;

  return (
    <div className="crawl-page">
      <div className="crawl-form">
        <div className="crawl-input-row">
          <input
            className="crawl-url-input"
            type="url"
            placeholder="https://suckhoedoisong.vn/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={status === 'running'}
          />
          <input
            className="crawl-pages-input"
            type="number"
            min={1}
            max={500}
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            disabled={status === 'running'}
            title="Số trang tối đa"
          />
          <button
            className="crawl-btn"
            onClick={handleStart}
            disabled={status === 'running'}
          >
            {status === 'running' ? 'Đang crawl...' : 'Bắt đầu'}
          </button>
        </div>
        {error && <p className="crawl-error">{error}</p>}
      </div>

      {status && (
        <div className="crawl-monitor">
          <div className="crawl-status-row">
            <span className={`crawl-badge crawl-badge--${status}`}>
              {status === 'running' && '● Đang chạy'}
              {status === 'completed' && '✓ Hoàn thành'}
              {status === 'failed' && '✗ Lỗi'}
            </span>
            <span className="crawl-count">
              {progress.pages_crawled} / {progress.max_pages} trang
            </span>
          </div>

          <div className="crawl-progress-bar">
            <div
              className="crawl-progress-fill"
              style={{ width: `${percent}%` }}
            />
          </div>

          <div className="crawl-log" ref={logRef}>
            {logs.length === 0 && status === 'running' && (
              <span className="crawl-log-placeholder">Đang khởi động...</span>
            )}
            {logs.map((line, i) => (
              <div key={i} className="crawl-log-line">{line}</div>
            ))}
            {status === 'completed' && (
              <div className="crawl-log-line crawl-log-done">
                ✓ Crawl hoàn tất — {progress.pages_crawled} bài đã lưu vào database.
              </div>
            )}
            {status === 'failed' && (
              <div className="crawl-log-line crawl-log-error">✗ Crawl thất bại.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

### Step 2: Tạo `CrawlPage.css`

```css
/* frontend/src/components/CrawlPage.css */

.crawl-page {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Form row */
.crawl-form {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
}

.crawl-input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.crawl-url-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.95rem;
  background: var(--color-bg);
  color: var(--color-text);
}

.crawl-url-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.crawl-pages-input {
  width: 90px;
  padding: 10px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.95rem;
  text-align: center;
  background: var(--color-bg);
  color: var(--color-text);
}

.crawl-btn {
  padding: 10px 22px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.crawl-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.crawl-error {
  margin-top: 10px;
  color: var(--color-error, #dc2626);
  font-size: 0.88rem;
}

/* Monitor */
.crawl-monitor {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.crawl-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.crawl-badge {
  font-size: 0.88rem;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
}

.crawl-badge--running  { background: #fef3c7; color: #92400e; }
.crawl-badge--completed { background: #d1fae5; color: #065f46; }
.crawl-badge--failed   { background: #fee2e2; color: #991b1b; }

.crawl-count {
  font-size: 0.88rem;
  color: var(--color-text-muted, #666);
}

/* Progress bar */
.crawl-progress-bar {
  height: 8px;
  background: var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}

.crawl-progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
  transition: width 0.4s ease;
}

/* Log terminal */
.crawl-log {
  background: #0f172a;
  color: #94a3b8;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  border-radius: 6px;
  padding: 14px 16px;
  max-height: 320px;
  overflow-y: auto;
}

.crawl-log-placeholder {
  color: #475569;
  font-style: italic;
}

.crawl-log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.crawl-log-done  { color: #4ade80; margin-top: 6px; }
.crawl-log-error { color: #f87171; margin-top: 6px; }
```

### Step 3: Commit

```bash
git add frontend/src/components/CrawlPage.jsx frontend/src/components/CrawlPage.css
git commit -m "feat: add CrawlPage component with progress bar and log terminal"
```

---

## Task 3: Frontend — Thêm tab navigation vào App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

### Step 1: Sửa `App.jsx` — thêm tab state và CrawlPage

```jsx
import React, { useState } from 'react';
import { analyzeText, analyzeUrl } from './services/api';
import Header from './components/Header';
import InputPanel from './components/InputPanel';
import EntityLegend from './components/EntityLegend';
import ResultsPanel from './components/ResultsPanel';
import SystemStats from './components/SystemStats';
import CrawlPage from './components/CrawlPage';  // <-- thêm
import './App.css';

function App() {
  const [tab, setTab] = useState('ner');  // <-- thêm
  const [inputType, setInputType] = useState('text');
  // ... (giữ nguyên các state cũ)

  return (
    <div className="page" onKeyDown={handleKeyDown}>
      <Header />

      {/* Tab navigation */}
      <nav className="tab-nav">
        <div className="tab-nav-inner">
          <button
            className={`tab-btn${tab === 'ner' ? ' tab-btn--active' : ''}`}
            onClick={() => setTab('ner')}
          >
            Phân tích NER
          </button>
          <button
            className={`tab-btn${tab === 'crawl' ? ' tab-btn--active' : ''}`}
            onClick={() => setTab('crawl')}
          >
            Thu thập dữ liệu
          </button>
        </div>
      </nav>

      <div className="content-wrap">
        {tab === 'ner' && (
          <>
            <div className="main-grid">
              <InputPanel ... />
              <EntityLegend />
            </div>
            {results && <ResultsPanel results={results} />}
            <SystemStats />
          </>
        )}

        {tab === 'crawl' && <CrawlPage />}
      </div>

      <footer className="site-footer">
        <p>Hệ thống Nhận diện Thực thể Y tế Tiếng Việt · PhoBERT + Ensemble Model</p>
      </footer>
    </div>
  );
}

export default App;
```

> **Lưu ý khi edit App.jsx:** Giữ nguyên toàn bộ logic NER (handleAnalyze, handleTypeChange, v.v.), chỉ thêm `tab` state + tab nav + `{tab === 'crawl' && <CrawlPage />}`.

### Step 2: Thêm CSS cho tab nav vào `App.css`

```css
/* Tab Navigation */
.tab-nav {
  background: var(--color-surface, #fff);
  border-bottom: 1px solid var(--color-border);
}

.tab-nav-inner {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  gap: 4px;
}

.tab-btn {
  padding: 12px 20px;
  border: none;
  border-bottom: 3px solid transparent;
  background: transparent;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--color-text-muted, #666);
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
  color: var(--color-text, #111);
}

.tab-btn--active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}
```

### Step 3: Commit

```bash
git add frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add tab navigation with Crawl page"
```

---

## Task 4: Deploy script

**Files:**
- Create: `deploy.sh`

### Step 1: Tạo `deploy.sh`

Script này chạy trên Windows qua Git Bash hoặc WSL.

```bash
#!/usr/bin/env bash
# deploy.sh — Deploy Medical NER lên VPS Linux qua SSH + PEM key
# Cách dùng: ./deploy.sh <pem_key_path> <user@server_ip>
# Ví dụ:     ./deploy.sh ~/.ssh/mykey.pem ubuntu@123.45.67.89

set -e

PEM_KEY="$1"
SERVER="$2"
REMOTE_DIR="/opt/medical-ner"

if [[ -z "$PEM_KEY" || -z "$SERVER" ]]; then
  echo "Usage: ./deploy.sh <path/to/key.pem> <user@server_ip>"
  exit 1
fi

SSH="ssh -i $PEM_KEY -o StrictHostKeyChecking=no $SERVER"
SCP="scp -i $PEM_KEY -o StrictHostKeyChecking=no"

echo "=== [1/4] Uploading project files ==="
# Rsync toàn bộ project (bỏ qua node_modules, __pycache__, .git)
rsync -az --delete \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude 'backend/data/*.db' \
  -e "ssh -i $PEM_KEY -o StrictHostKeyChecking=no" \
  ./ "$SERVER:$REMOTE_DIR/"

echo "=== [2/4] Setting up server dependencies ==="
$SSH "
  cd $REMOTE_DIR
  # Cài Docker + Docker Compose nếu chưa có
  if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker \$USER
    echo 'Docker installed.'
  fi
  if ! command -v docker compose &>/dev/null; then
    sudo apt-get install -y docker-compose-plugin
  fi
"

echo "=== [3/4] Building and starting containers ==="
$SSH "
  cd $REMOTE_DIR
  docker compose down --remove-orphans || true
  docker compose build --no-cache
  docker compose up -d
"

echo "=== [4/4] Health check ==="
sleep 8
$SSH "curl -sf http://localhost:8000/api/health && echo 'Backend OK'" || echo "Backend chưa sẵn sàng, chờ thêm..."
$SSH "curl -sf http://localhost:80 > /dev/null && echo 'Frontend OK'" || echo "Frontend chưa sẵn sàng."

echo ""
echo "Deploy xong!"
echo "Truy cập: http://$(echo $SERVER | cut -d@ -f2)"
```

### Step 2: Tạo file `.env.production` mẫu (nếu chưa có)

Tạo file `.env.example` ở root nếu chưa có:

```bash
# .env.example
SECRET_KEY=change-this-to-a-random-string-in-production
```

Khi deploy lên server, copy thành `.env` và điền giá trị thật:
```bash
cp .env.example .env
# Edit .env trên server:
ssh -i key.pem user@server "nano /opt/medical-ner/.env"
```

### Step 3: Commit

```bash
git add deploy.sh
git commit -m "feat: add SSH deploy script for Linux VPS"
```

---

## Cách chạy sau khi deploy

```bash
# Từ Windows Git Bash / WSL:
chmod +x deploy.sh
./deploy.sh ~/.ssh/your-key.pem ubuntu@YOUR_SERVER_IP
```

Frontend sẽ truy cập tại: `http://YOUR_SERVER_IP`
Backend API tại: `http://YOUR_SERVER_IP:8000`

---

## Thứ tự thực hiện

1. Task 1 (backend progress) → Task 2 (CrawlPage component) → Task 3 (App.jsx nav) → Task 4 (deploy script)
2. Test local trước: `docker compose up` rồi mở `http://localhost`
3. Deploy sau khi test xong
