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
