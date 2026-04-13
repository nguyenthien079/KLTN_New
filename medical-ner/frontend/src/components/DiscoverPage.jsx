import React, { useState, useEffect, useRef } from 'react';
import { startDiscovery, getDiscoveryStatus } from '../services/api';
import './DiscoverPage.css';

const LS_KEY = 'medical_ner_discover_job_id';

export default function DiscoverPage({ isBlocked, onStatusChange, onCrawlNow }) {
  const [url, setUrl] = useState('');
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // null | 'running' | 'completed' | 'failed'
  const [urlCount, setUrlCount] = useState(0);
  const [logs, setLogs] = useState([]);
  const [urls, setUrls] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState(null);
  const [showLog, setShowLog] = useState(false);
  const logRef = useRef(null);
  const pollRef = useRef(null);

  // Restore jobId from localStorage on mount (resume after navigation)
  useEffect(() => {
    const savedJobId = localStorage.getItem(LS_KEY);
    if (savedJobId) {
      setStatus('running');
      setJobId(savedJobId);
    }
  }, []);

  // Notify parent when running status changes
  useEffect(() => {
    if (onStatusChange) onStatusChange(status);
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll log
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
        const data = await getDiscoveryStatus(jobId);
        setStatus(data.status);
        setUrlCount(data.url_count);
        setLogs(data.logs || []);
        setUrls(data.urls || []);
        if (data.status === 'completed') {
          clearInterval(pollRef.current);
          localStorage.removeItem(LS_KEY);
          // Auto-select all on completion
          setSelected(new Set(data.urls || []));
        }
        if (data.status === 'failed') {
          clearInterval(pollRef.current);
          localStorage.removeItem(LS_KEY);
        }
      } catch {
        clearInterval(pollRef.current);
        setStatus('failed');
        setError('Mất kết nối — không thể theo dõi tiến trình.');
        localStorage.removeItem(LS_KEY);
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
    setStatus('running');
    setUrlCount(0);
    setShowLog(false);
    try {
      const data = await startDiscovery(url.trim());
      setJobId(data.job_id);
      localStorage.setItem(LS_KEY, data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu tìm kiếm.');
      localStorage.removeItem(LS_KEY);
    }
  };

  const handleReset = () => {
    setStatus(null);
    setJobId(null);
    setLogs([]);
    setUrls([]);
    setSelected(new Set());
    setUrlCount(0);
    setError(null);
    setShowLog(false);
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

  const handleExport = (format) => {
    const list = urls.length > 0 ? urls : [];
    // Use the searched domain as filename base, fallback to 'discovered-urls'
    let baseName = 'discovered-urls';
    try {
      const parsed = new URL(url);
      // hostname e.g. "bachmai.hanoi.gov.vn", strip leading "www."
      baseName = parsed.hostname.replace(/^www\./, '');
    } catch {
      // url might be empty or invalid — keep default
    }

    let content, filename, type;
    if (format === 'json') {
      content = JSON.stringify({ url, total: list.length, urls: list }, null, 2);
      filename = `${baseName}.json`;
      type = 'application/json';
    } else {
      content = 'url\n' + list.join('\n');
      filename = `${baseName}.csv`;
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
  const isDone = status === 'completed' || status === 'failed';

  // ── Completed state ──────────────────────────────────────────────────────────
  if (isDone) {
    return (
      <div className="discover-page">
        {/* Compact "done" header */}
        <div className="discover-done-header">
          <div className="discover-done-meta">
            <span className={`discover-badge discover-badge--${status}`}>
              {status === 'completed' ? '✓ Hoàn thành' : '✗ Lỗi'}
            </span>
            <span className="discover-done-url" title={url}>{url}</span>
            <span className="discover-done-count">{urlCount} URLs</span>
          </div>
          <div className="discover-done-actions-right">
            {logs.length > 0 && (
              <button
                className="discover-log-toggle"
                onClick={() => setShowLog(v => !v)}
              >
                {showLog ? 'Ẩn log' : 'Xem log'}
              </button>
            )}
            <button className="discover-reset-btn" onClick={handleReset}>
              Tìm lại
            </button>
          </div>
        </div>

        {/* Collapsible log */}
        {showLog && (
          <div className="discover-log discover-log--collapsed" ref={logRef}>
            {logs.map((line, i) => (
              <div key={i} className="discover-log-line">{line}</div>
            ))}
          </div>
        )}

        {/* URL list — main content */}
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

            {/* Primary CTA */}
            {onCrawlNow && (
              <div className="discover-crawl-cta-row">
                <span className="discover-crawl-cta-hint">
                  {selected.size} / {urls.length} URL đã chọn
                </span>
                <button
                  className="discover-crawl-cta-btn"
                  disabled={selected.size === 0}
                  onClick={() => onCrawlNow(url, Array.from(selected))}
                >
                  Bắt đầu crawl {selected.size} URLs →
                </button>
              </div>
            )}
          </div>
        )}

        {status === 'failed' && (
          <p className="discover-error">{error || 'Tìm kiếm thất bại.'}</p>
        )}
      </div>
    );
  }

  // ── Normal / running state ───────────────────────────────────────────────────
  return (
    <div className="discover-page">
      {/* Input form */}
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
            disabled={status === 'running' || isBlocked}
            title={isBlocked ? 'Đang crawl — vui lòng chờ crawl xong.' : ''}
          >
            {status === 'running' ? 'Đang tìm...' : 'Bắt đầu tìm'}
          </button>
        </div>
        {isBlocked && status !== 'running' && (
          <p className="discover-error">Đang crawl — không thể bắt đầu tìm site cùng lúc.</p>
        )}
        {error && <p className="discover-error">{error}</p>}
      </div>

      {/* Running monitor */}
      {status === 'running' && (
        <div className="discover-monitor">
          <div className="discover-status-row">
            <span className="discover-badge discover-badge--running">● Đang tìm</span>
            <span className="discover-count">{urlCount} URLs tìm được</span>
          </div>

          <div className="discover-progress-bar">
            <div className="discover-progress-fill discover-progress-fill--indeterminate" />
          </div>

          <div className="discover-log" ref={logRef}>
            {logs.length === 0 && (
              <span className="discover-log-placeholder">Đang khởi động...</span>
            )}
            {logs.map((line, i) => (
              <div key={i} className="discover-log-line">{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
