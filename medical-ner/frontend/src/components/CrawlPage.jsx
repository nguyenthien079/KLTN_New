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

  // Polling — starts when jobId is set, stops when done
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
