import React, { useState, useEffect, useRef } from 'react';
import { startCrawl, getCrawlStatus } from '../services/api';
import DiscoverPage from './DiscoverPage';
import './CrawlPage.css';

const LS_KEY = 'medical_ner_crawl_job_id';

export default function CrawlPage() {
  const [subTab, setSubTab] = useState('discover');
  const [url, setUrl] = useState('');
  const [pendingUrls, setPendingUrls] = useState(null); // URL list from discovery
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // null | 'running' | 'completed' | 'failed'
  const [progress, setProgress] = useState({ pages_crawled: 0, urls_processed: 0, total_urls: null });
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const [discoverRunning, setDiscoverRunning] = useState(false);
  const logRef = useRef(null);
  const pollRef = useRef(null);

  // Restore crawl jobId from localStorage on mount (resume after navigation)
  useEffect(() => {
    const savedJobId = localStorage.getItem(LS_KEY);
    if (savedJobId) {
      setStatus('running');
      setJobId(savedJobId);
    }
    // Also initialize discoverRunning from localStorage so mutual exclusion works immediately
    if (localStorage.getItem('medical_ner_discover_job_id')) {
      setDiscoverRunning(true);
    }
  }, []);

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
        if (data.status === 'failed' && data.error) {
          setError(data.error);
        }
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current);
          localStorage.removeItem(LS_KEY);
        }
      } catch {
        clearInterval(pollRef.current);
        setStatus('failed');
        setError('Mất kết nối — không thể theo dõi tiến trình crawl.');
        localStorage.removeItem(LS_KEY);
      }
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [jobId]);

  const handleStart = async () => {
    if (!url.trim() && !pendingUrls) { setError('Vui lòng nhập URL.'); return; }
    setError(null);
    setLogs([]);
    setProgress({ pages_crawled: 0, urls_processed: 0, total_urls: pendingUrls ? pendingUrls.length : null });
    setStatus('running');
    try {
      const data = await startCrawl(url.trim(), pendingUrls);
      setJobId(data.job_id);
      localStorage.setItem(LS_KEY, data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu crawl.');
      localStorage.removeItem(LS_KEY);
    }
  };

  // Called by DiscoverPage: receives base URL + selected URL list
  const handleCrawlNow = (discoverUrl, selectedUrls) => {
    setUrl(discoverUrl);
    setPendingUrls(selectedUrls && selectedUrls.length > 0 ? selectedUrls : null);
    setSubTab('crawl');
  };

  const crawlRunning = status === 'running';

  return (
    <div className="crawl-page">
      {/* Sub-tab nav */}
      <div className="crawl-subtab-nav">
        <button
          className={`crawl-subtab-btn${subTab === 'discover' ? ' crawl-subtab-btn--active' : ''}`}
          onClick={() => setSubTab('discover')}
        >
          Tìm site
          {discoverRunning && <span className="crawl-subtab-running-dot" />}
        </button>
        <button
          className={`crawl-subtab-btn${subTab === 'crawl' ? ' crawl-subtab-btn--active' : ''}`}
          onClick={() => setSubTab('crawl')}
        >
          Crawl
          {crawlRunning && <span className="crawl-subtab-running-dot" />}
        </button>
      </div>

      {/*
        Render both panels always — only toggle visibility.
        This keeps polling and state alive when switching subtabs.
      */}
      <div style={{ display: subTab === 'discover' ? 'block' : 'none' }}>
        <p className="crawl-tab-note">Tìm site chỉ quét và liệt kê URL — không crawl nội dung bài viết.</p>
        <DiscoverPage
          isBlocked={crawlRunning}
          onStatusChange={(s) => setDiscoverRunning(s === 'running')}
          onCrawlNow={handleCrawlNow}
        />
      </div>

      <div style={{ display: subTab === 'crawl' ? 'block' : 'none' }}>
        <p className="crawl-tab-note">Crawl trực tiếp nội dung bài viết từ URL — không tìm kiếm thêm site.</p>

        <div className="crawl-form">
          <div className="crawl-input-row">
            <input
              className="crawl-url-input"
              type="url"
              placeholder="https://suckhoedoisong.vn/..."
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                // If user manually changes URL, discard the pending URL list
                setPendingUrls(null);
              }}
              disabled={crawlRunning}
            />
            <button
              className="crawl-btn"
              onClick={handleStart}
              disabled={crawlRunning || discoverRunning}
              title={discoverRunning ? 'Đang tìm site — vui lòng chờ xong rồi crawl.' : ''}
            >
              {crawlRunning ? 'Đang crawl...' : 'Bắt đầu'}
            </button>
          </div>

          {/* Show source-from-discovery badge */}
          {pendingUrls && !crawlRunning && !status && (
            <div className="crawl-source-badge">
              Từ Tìm site: <strong>{pendingUrls.length} URLs đã chọn</strong> — crawl chính xác danh sách này
            </div>
          )}
          {!pendingUrls && !crawlRunning && !status && url && (
            <div className="crawl-source-badge crawl-source-badge--manual">
              Chế độ tự khám phá — crawl BFS từ URL này
            </div>
          )}

          {discoverRunning && !crawlRunning && (
            <p className="crawl-error">Đang tìm site — không thể bắt đầu crawl cùng lúc.</p>
          )}
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
                {progress.total_urls ? (
                  // List mode: show processed/total + saved count
                  <>
                    <span className="crawl-count-processed">
                      {progress.urls_processed} / {progress.total_urls} URLs xử lý
                    </span>
                    <span className="crawl-count-saved">
                      {progress.pages_crawled} bài lưu
                    </span>
                  </>
                ) : (
                  // BFS mode
                  `${progress.pages_crawled} trang đã crawl`
                )}
              </span>
            </div>

            {/* Determinate bar (list mode) uses urls_processed for reliable 100% */}
            <div className="crawl-progress-bar">
              {progress.total_urls ? (
                <div
                  className="crawl-progress-fill crawl-progress-fill--determinate"
                  style={{ width: status === 'completed' ? '100%' : `${Math.min(100, (progress.urls_processed / progress.total_urls) * 100)}%` }}
                />
              ) : (
                <div className={`crawl-progress-fill${crawlRunning ? ' crawl-progress-fill--indeterminate' : ' crawl-progress-fill--done'}`} />
              )}
            </div>

            <div className="crawl-log" ref={logRef}>
              {logs.length === 0 && crawlRunning && (
                <span className="crawl-log-placeholder">Đang khởi động...</span>
              )}
              {logs.map((line, i) => (
                <div key={i} className="crawl-log-line">{line}</div>
              ))}
              {status === 'completed' && (
                <div className="crawl-log-line crawl-log-done">
                  ✓ Crawl hoàn tất —{progress.total_urls
                    ? ` xử lý ${progress.urls_processed}/${progress.total_urls} URLs, lưu ${progress.pages_crawled} bài.`
                    : ` lưu ${progress.pages_crawled} bài vào database.`}
                </div>
              )}
              {status === 'failed' && (
                <div className="crawl-log-line crawl-log-error">
                  ✗ Crawl thất bại{error ? `: ${error}` : '.'}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
