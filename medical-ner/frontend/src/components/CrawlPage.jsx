import React, { useState, useEffect, useRef } from 'react';
import { startCrawl, getCrawlStatus } from '../services/api';
import DiscoverPage from './DiscoverPage';
import './CrawlPage.css';

export default function CrawlPage() {
  const [subTab, setSubTab] = useState('discover');
  const [url, setUrl] = useState('');
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
    if (!jobId) return;

    clearInterval(pollRef.current);
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
        setStatus('failed');
        setError('Mất kết nối — không thể theo dõi tiến trình crawl.');
      }
    }, 2000);

    return () => clearInterval(pollRef.current);
  }, [jobId]);

  const handleStart = async () => {
    if (!url.trim()) {
      setError('Vui lòng nhập URL.');
      return;
    }
    setError(null);
    setLogs([]);
    setProgress({ pages_crawled: 0 });
    setStatus('running');
    try {
      const data = await startCrawl(url.trim());
      setJobId(data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu crawl.');
    }
  };

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

      {subTab === 'crawl' && <div className="crawl-form">
        <div className="crawl-input-row">
          <input
            className="crawl-url-input"
            type="url"
            placeholder="https://suckhoedoisong.vn/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={status === 'running'}
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
      </div>}

      {subTab === 'crawl' && status && (
        <div className="crawl-monitor">
          <div className="crawl-status-row">
            <span className={`crawl-badge crawl-badge--${status}`}>
              {status === 'running' && '● Đang chạy'}
              {status === 'completed' && '✓ Hoàn thành'}
              {status === 'failed' && '✗ Lỗi'}
            </span>
            <span className="crawl-count">
              {progress.pages_crawled} trang đã crawl
            </span>
          </div>

          <div className="crawl-progress-bar">
            <div className={`crawl-progress-fill${status === 'running' ? ' crawl-progress-fill--indeterminate' : ' crawl-progress-fill--done'}`} />
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
                ✓ Crawl hoàn tất — lưu {progress.pages_crawled} bài vào database.
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
