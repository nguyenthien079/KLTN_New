# Site Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Thêm tính năng "Tìm site" — người dùng nhập URL, hệ thống tìm toàn bộ sub-URL trong domain (homepage links + sitemap.xml + BFS 2 cấp), hiển thị log real-time, cho phép chọn URL để crawl hoặc export JSON/CSV.

**Architecture:** Backend thêm `SiteDiscovery` class trong `discovery.py` (tái dùng `HTMLExtractor.fetch_html` + BeautifulSoup), 2 endpoint mới trong `routers/crawler.py` (`POST /api/crawl/discover`, `GET /api/crawl/discover/{job_id}`), lưu in-memory vào `discovery_jobs` dict. Frontend thêm `DiscoverPage` component mới, `CrawlPage` wrap 2 sub-tab: "Tìm site" và "Crawl".

**Tech Stack:** FastAPI BackgroundTasks, BeautifulSoup (đã có), httpx (đã có), React 18, Axios

---

## Task 1: Backend — `SiteDiscovery` class

**Files:**
- Create: `backend/app/crawler/discovery.py`

### Step 1: Tạo `discovery.py`

```python
# backend/app/crawler/discovery.py
import asyncio
from typing import Callable, List, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from app.crawler.extractor import HTMLExtractor


class SiteDiscovery:
    """Discover all URLs within a domain (homepage + sitemap + BFS 2 levels)"""

    def __init__(self):
        self.extractor = HTMLExtractor()

    async def discover(
        self,
        start_url: str,
        on_progress: Optional[Callable[[int, str], None]] = None
    ) -> List[str]:
        """
        Find all unique URLs in the same domain as start_url.
        Steps:
          1. Fetch homepage → collect links
          2. Try /sitemap.xml → collect <loc> URLs
          3. BFS up to depth 2 on found URLs → collect more links
        Returns sorted list of unique URLs.
        """
        parsed = urlparse(start_url)
        domain = parsed.netloc
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        found: Set[str] = set()
        visited: Set[str] = set()

        def log(url: str):
            found.add(url)
            if on_progress:
                on_progress(len(found), url)

        # Step 1: homepage
        html = await self.extractor.fetch_html(start_url)
        if html:
            for link in self._extract_links(html, start_url, domain):
                if link not in found:
                    log(link)
        visited.add(start_url)

        # Step 2: sitemap.xml
        sitemap_url = f"{base_url}/sitemap.xml"
        sitemap_html = await self.extractor.fetch_html(sitemap_url)
        if sitemap_html:
            for link in self._extract_sitemap_urls(sitemap_html, domain):
                if link not in found:
                    log(link)

        # Step 3: BFS depth 2 on found URLs (cap at 200 to avoid runaway)
        queue = list(found)[:200]
        for url in queue:
            if url in visited:
                continue
            visited.add(url)
            await asyncio.sleep(0.1)  # polite rate limit
            html = await self.extractor.fetch_html(url)
            if not html:
                continue
            for link in self._extract_links(html, url, domain):
                if link not in found:
                    log(link)
                    if len(found) >= 1000:  # hard cap
                        break
            if len(found) >= 1000:
                break

        return sorted(found)

    def _extract_links(self, html: str, base_url: str, domain: str) -> List[str]:
        """Parse <a href> tags, return same-domain URLs only."""
        soup = BeautifulSoup(html, 'lxml')
        links = []
        for tag in soup.find_all('a', href=True):
            url = urljoin(base_url, tag['href'])
            parsed = urlparse(url)
            if parsed.netloc == domain and parsed.scheme in ('http', 'https'):
                # Strip fragment
                clean = url.split('#')[0].rstrip('/')
                if clean and clean not in links:
                    links.append(clean)
        return links

    def _extract_sitemap_urls(self, xml: str, domain: str) -> List[str]:
        """Parse sitemap XML, return same-domain <loc> URLs."""
        soup = BeautifulSoup(xml, 'lxml-xml')
        urls = []
        for loc in soup.find_all('loc'):
            url = loc.get_text(strip=True)
            if urlparse(url).netloc == domain:
                urls.append(url.rstrip('/'))
        return urls
```

### Step 2: Verify file tạo đúng

Đọc lại `backend/app/crawler/discovery.py` và kiểm tra:
- Class `SiteDiscovery` có method `discover(start_url, on_progress=None)`
- `_extract_links` và `_extract_sitemap_urls` có mặt
- Import đúng: `HTMLExtractor` từ `app.crawler.extractor`

### Step 3: Commit

```bash
git add backend/app/crawler/discovery.py
git commit -m "feat: add SiteDiscovery class for URL discovery"
```

---

## Task 2: Backend — Discovery endpoints trong router

**Files:**
- Modify: `backend/app/routers/crawler.py`

### Step 1: Thêm `discovery_jobs` dict và Pydantic models

Sau dòng `crawl_jobs: dict = {}`, thêm:

```python
discovery_jobs: dict = {}


class DiscoverRequest(BaseModel):
    url: str


class DiscoverStatusResponse(BaseModel):
    job_id: str
    status: str
    url_count: int
    logs: list[str] = []
    urls: list[str] = []
```

### Step 2: Thêm `POST /api/crawl/discover` endpoint

```python
@router.post("/discover")
async def start_discovery(
    request: DiscoverRequest,
    background_tasks: BackgroundTasks,
):
    """Start a background site discovery job"""
    job_id = str(uuid.uuid4())

    discovery_jobs[job_id] = {
        "status": "running",
        "url": request.url,
        "url_count": 0,
        "logs": [],
        "urls": [],
    }

    background_tasks.add_task(run_discovery_job, job_id, request.url)

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Discovery started for {request.url}",
    }
```

### Step 3: Thêm `GET /api/crawl/discover/{job_id}` endpoint

```python
@router.get("/discover/{job_id}", response_model=DiscoverStatusResponse)
async def get_discovery_status(job_id: str):
    """Get status of a discovery job"""
    from fastapi import HTTPException
    if job_id not in discovery_jobs:
        raise HTTPException(status_code=404, detail="Discovery job not found")

    job = discovery_jobs[job_id]
    return DiscoverStatusResponse(
        job_id=job_id,
        status=job["status"],
        url_count=job.get("url_count", 0),
        logs=job.get("logs", []),
        urls=job.get("urls", []),
    )
```

### Step 4: Thêm `run_discovery_job` background task

```python
async def run_discovery_job(job_id: str, url: str):
    """Background task that runs site discovery"""
    from app.crawler.discovery import SiteDiscovery

    try:
        discovery = SiteDiscovery()

        def progress_callback(count: int, found_url: str):
            discovery_jobs[job_id]["url_count"] = count
            discovery_jobs[job_id]["logs"].append(f"[{count}] {found_url}")
            discovery_jobs[job_id]["urls"].append(found_url)

        urls = await discovery.discover(url, on_progress=progress_callback)

        discovery_jobs[job_id]["status"] = "completed"
        discovery_jobs[job_id]["url_count"] = len(urls)

    except Exception as e:
        discovery_jobs[job_id]["status"] = "failed"
        discovery_jobs[job_id]["error"] = str(e)
```

### Step 5: Commit

```bash
git add backend/app/routers/crawler.py
git commit -m "feat: add discovery endpoints POST /discover and GET /discover/{job_id}"
```

---

## Task 3: Frontend — API functions

**Files:**
- Modify: `frontend/src/services/api.js`

### Step 1: Thêm 2 functions

Sau `getCrawlStatus`, thêm:

```js
export const startDiscovery = async (url) => {
  const response = await api.post('/api/crawl/discover', { url });
  return response.data;
};

export const getDiscoveryStatus = async (jobId) => {
  const response = await api.get(`/api/crawl/discover/${jobId}`);
  return response.data;
};
```

### Step 2: Commit

```bash
git add frontend/src/services/api.js
git commit -m "feat: add startDiscovery and getDiscoveryStatus API functions"
```

---

## Task 4: Frontend — `DiscoverPage` component

**Files:**
- Create: `frontend/src/components/DiscoverPage.jsx`
- Create: `frontend/src/components/DiscoverPage.css`

### Step 1: Tạo `DiscoverPage.jsx`

```jsx
// frontend/src/components/DiscoverPage.jsx
import React, { useState, useEffect, useRef } from 'react';
import { startDiscovery, getDiscoveryStatus, startCrawl } from '../services/api';
import './DiscoverPage.css';

export default function DiscoverPage() {
  const [url, setUrl] = useState('');
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // null | 'running' | 'completed' | 'failed'
  const [urlCount, setUrlCount] = useState(0);
  const [logs, setLogs] = useState([]);
  const [urls, setUrls] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState(null);
  const [crawlMsg, setCrawlMsg] = useState(null);
  const logRef = useRef(null);
  const pollRef = useRef(null);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Polling
  useEffect(() => {
    if (!jobId) return;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await getDiscoveryStatus(jobId);
        setStatus(data.status);
        setUrlCount(data.url_count);
        setLogs(data.logs || []);
        setUrls(data.urls || []);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current);
        }
      } catch {
        clearInterval(pollRef.current);
        setStatus('failed');
        setError('Mất kết nối — không thể theo dõi tiến trình.');
      }
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [jobId]);

  const handleStart = async () => {
    if (!url.trim()) { setError('Vui lòng nhập URL.'); return; }
    setError(null);
    setLogs([]);
    setUrls([]);
    setSelected(new Set());
    setCrawlMsg(null);
    setStatus('running');
    setUrlCount(0);
    try {
      const data = await startDiscovery(url.trim());
      setJobId(data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu tìm kiếm.');
    }
  };

  const toggleSelect = (u) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(u) ? next.delete(u) : next.add(u);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === urls.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(urls));
    }
  };

  const handleCrawlSelected = async () => {
    if (selected.size === 0) return;
    setCrawlMsg(null);
    try {
      for (const u of selected) {
        await startCrawl(u);
      }
      setCrawlMsg(`Đã bắt đầu crawl ${selected.size} URL. Chuyển sang tab "Crawl" để theo dõi.`);
    } catch (err) {
      setCrawlMsg('Lỗi khi bắt đầu crawl: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleExport = (format) => {
    const list = urls.length > 0 ? urls : [];
    let content, filename, type;
    if (format === 'json') {
      content = JSON.stringify({ url, total: list.length, urls: list }, null, 2);
      filename = 'discovered-urls.json';
      type = 'application/json';
    } else {
      content = 'url\n' + list.join('\n');
      filename = 'discovered-urls.csv';
      type = 'text/csv';
    }
    const blob = new Blob([content], { type });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const allChecked = urls.length > 0 && selected.size === urls.length;

  return (
    <div className="discover-page">
      {/* Input */}
      <div className="discover-form">
        <div className="discover-input-row">
          <input
            className="discover-url-input"
            type="url"
            placeholder="https://suckhoedoisong.vn"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={status === 'running'}
          />
          <button
            className="discover-btn"
            onClick={handleStart}
            disabled={status === 'running'}
          >
            {status === 'running' ? 'Đang tìm...' : 'Bắt đầu tìm'}
          </button>
        </div>
        {error && <p className="discover-error">{error}</p>}
      </div>

      {/* Monitor */}
      {status && (
        <div className="discover-monitor">
          <div className="discover-status-row">
            <span className={`discover-badge discover-badge--${status}`}>
              {status === 'running' && '● Đang tìm'}
              {status === 'completed' && '✓ Hoàn thành'}
              {status === 'failed' && '✗ Lỗi'}
            </span>
            <span className="discover-count">{urlCount} URLs tìm được</span>
          </div>

          <div className="discover-progress-bar">
            <div className={`discover-progress-fill${status === 'running' ? ' discover-progress-fill--indeterminate' : ' discover-progress-fill--done'}`} />
          </div>

          <div className="discover-log" ref={logRef}>
            {logs.length === 0 && status === 'running' && (
              <span className="discover-log-placeholder">Đang khởi động...</span>
            )}
            {logs.map((line, i) => (
              <div key={i} className="discover-log-line">{line}</div>
            ))}
            {status === 'completed' && (
              <div className="discover-log-line discover-log-done">
                ✓ Tìm xong — {urlCount} URLs trong domain.
              </div>
            )}
            {status === 'failed' && (
              <div className="discover-log-line discover-log-error">✗ Tìm kiếm thất bại.</div>
            )}
          </div>
        </div>
      )}

      {/* URL list */}
      {urls.length > 0 && (
        <div className="discover-results">
          <div className="discover-results-header">
            <label className="discover-check-all">
              <input
                type="checkbox"
                checked={allChecked}
                onChange={toggleAll}
              />
              Chọn tất cả ({urls.length})
            </label>
            <div className="discover-export-btns">
              <button className="discover-export-btn" onClick={() => handleExport('json')}>
                Export JSON
              </button>
              <button className="discover-export-btn" onClick={() => handleExport('csv')}>
                Export CSV
              </button>
            </div>
          </div>

          <div className="discover-url-list">
            {urls.map((u, i) => (
              <label key={i} className="discover-url-item">
                <input
                  type="checkbox"
                  checked={selected.has(u)}
                  onChange={() => toggleSelect(u)}
                />
                <span className="discover-url-text">{u}</span>
              </label>
            ))}
          </div>

          <div className="discover-actions">
            {crawlMsg && <p className="discover-crawl-msg">{crawlMsg}</p>}
            <button
              className="discover-crawl-btn"
              onClick={handleCrawlSelected}
              disabled={selected.size === 0}
            >
              Crawl đã chọn ({selected.size})
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Step 2: Tạo `DiscoverPage.css`

```css
/* frontend/src/components/DiscoverPage.css */

.discover-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Form */
.discover-form {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
}

.discover-input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.discover-url-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.95rem;
  background: var(--color-bg);
  color: var(--color-text);
}

.discover-url-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.discover-btn {
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

.discover-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.discover-error {
  margin-top: 10px;
  color: var(--color-error, #dc2626);
  font-size: 0.88rem;
}

/* Monitor */
.discover-monitor {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.discover-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.discover-badge {
  font-size: 0.88rem;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
}

.discover-badge--running   { background: #fef3c7; color: #92400e; }
.discover-badge--completed { background: #d1fae5; color: #065f46; }
.discover-badge--failed    { background: var(--color-error-bg); color: var(--color-error); }

.discover-count {
  font-size: 0.88rem;
  color: var(--color-text-muted, #64748b);
}

/* Progress bar */
.discover-progress-bar {
  height: 8px;
  background: var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}

.discover-progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
}

@keyframes discover-slide {
  0%   { transform: translateX(-100%); width: 40%; }
  100% { transform: translateX(300%);  width: 40%; }
}

.discover-progress-fill--indeterminate {
  width: 40%;
  animation: discover-slide 1.4s ease-in-out infinite;
}

.discover-progress-fill--done {
  width: 100%;
}

/* Log terminal */
.discover-log {
  background: #0f172a;
  color: #94a3b8;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  border-radius: 6px;
  padding: 14px 16px;
  max-height: 240px;
  overflow-y: auto;
}

.discover-log-placeholder { color: #475569; font-style: italic; }
.discover-log-line { white-space: pre-wrap; word-break: break-all; }
.discover-log-done  { color: #4ade80; margin-top: 6px; }
.discover-log-error { color: #f87171; margin-top: 6px; }

/* Results */
.discover-results {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.discover-results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.discover-check-all {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-text);
}

.discover-export-btns {
  display: flex;
  gap: 8px;
}

.discover-export-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.85rem;
  cursor: pointer;
}

.discover-export-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* URL list */
.discover-url-list {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 12px;
}

.discover-url-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  cursor: pointer;
  font-size: 0.88rem;
}

.discover-url-item:hover .discover-url-text {
  color: var(--color-primary);
}

.discover-url-text {
  color: var(--color-text);
  word-break: break-all;
}

/* Actions */
.discover-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}

.discover-crawl-msg {
  font-size: 0.88rem;
  color: var(--color-primary);
}

.discover-crawl-btn {
  padding: 10px 24px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
}

.discover-crawl-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

### Step 3: Commit

```bash
git add frontend/src/components/DiscoverPage.jsx frontend/src/components/DiscoverPage.css
git commit -m "feat: add DiscoverPage component with URL list, checkboxes, export and crawl actions"
```

---

## Task 5: Frontend — Sub-tabs trong `CrawlPage`

**Files:**
- Modify: `frontend/src/components/CrawlPage.jsx`
- Modify: `frontend/src/components/CrawlPage.css`

### Step 1: Sửa `CrawlPage.jsx`

Thêm import `DiscoverPage` và `subTab` state, wrap nội dung trong sub-tab:

```jsx
import React, { useState, useEffect, useRef } from 'react';
import { startCrawl, getCrawlStatus } from '../services/api';
import DiscoverPage from './DiscoverPage';
import './CrawlPage.css';

export default function CrawlPage() {
  const [subTab, setSubTab] = useState('discover');
  // ... (giữ nguyên tất cả state hiện tại)

  return (
    <div className="crawl-page">
      {/* Sub-tab nav */}
      <div className="crawl-subtab-nav">
        <button
          className={`crawl-subtab-btn${subTab === 'discover' ? ' crawl-subtab-btn--active' : ''}`}
          onClick={() => setSubTab('discover')}
        >
          Tìm site
        </button>
        <button
          className={`crawl-subtab-btn${subTab === 'crawl' ? ' crawl-subtab-btn--active' : ''}`}
          onClick={() => setSubTab('crawl')}
        >
          Crawl
        </button>
      </div>

      {subTab === 'discover' && <DiscoverPage />}

      {subTab === 'crawl' && (
        <>
          {/* Giữ nguyên toàn bộ JSX crawl form + monitor hiện tại */}
        </>
      )}
    </div>
  );
}
```

> **Quan trọng khi edit:** Giữ NGUYÊN toàn bộ logic crawl (state, polling, handleStart, JSX form + monitor). Chỉ thêm `subTab` state, sub-tab nav buttons, import DiscoverPage, và wrap crawl content trong `{subTab === 'crawl' && ...}`.

### Step 2: Thêm CSS sub-tab vào `CrawlPage.css`

Thêm vào cuối file:

```css
/* Sub-tab navigation */
.crawl-subtab-nav {
  display: flex;
  gap: 6px;
  border-bottom: 2px solid var(--color-border);
  padding-bottom: 0;
}

.crawl-subtab-btn {
  padding: 8px 18px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font-size: 0.92rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--color-text-muted, #64748b);
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}

.crawl-subtab-btn:hover {
  color: var(--color-text);
}

.crawl-subtab-btn--active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}
```

### Step 3: Commit

```bash
git add frontend/src/components/CrawlPage.jsx frontend/src/components/CrawlPage.css
git commit -m "feat: add Tìm site / Crawl sub-tabs to CrawlPage"
```

---

## Thứ tự thực hiện

Task 1 → Task 2 → Task 3 → Task 4 → Task 5

Mỗi task độc lập, commit sau mỗi task.
