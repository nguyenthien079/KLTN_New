import React, { useState, useEffect, useRef } from 'react';
import { startFilter, getFilterStatus, startPipeline, getPipelineStatus } from '../services/api';
import './PipelinePage.css';

function JobSection({ title, description, onStart, pollFn }) {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const logRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => {
    if (!jobId) return;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await pollFn(jobId);
        setStatus(data.status);
        setLogs(data.logs || []);
        if (data.result) setResult(data.result);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current);
        }
      } catch {
        clearInterval(pollRef.current);
        setStatus('failed');
      }
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [jobId, pollFn]);

  const handleStart = async () => {
    setError(null);
    setLogs([]);
    setResult(null);
    setStatus('running');
    try {
      const data = await onStart();
      setJobId(data.job_id);
    } catch (err) {
      setStatus('failed');
      setError(err.response?.data?.detail || 'Không thể bắt đầu.');
    }
  };

  return (
    <div className="pipeline-section">
      <div className="pipeline-section-header">
        <div>
          <h3 className="pipeline-section-title">{title}</h3>
          <p className="pipeline-section-desc">{description}</p>
        </div>
        <button
          className="pipeline-btn"
          onClick={handleStart}
          disabled={status === 'running'}
        >
          {status === 'running' ? 'Đang chạy...' : 'Chạy'}
        </button>
      </div>

      {error && <p className="pipeline-error">{error}</p>}

      {status && (
        <>
          <div className="pipeline-status-row">
            <span className={`pipeline-badge pipeline-badge--${status}`}>
              {status === 'running' && '● Đang chạy'}
              {status === 'completed' && '✓ Hoàn thành'}
              {status === 'failed' && '✗ Lỗi'}
            </span>
            {result && (
              <span className="pipeline-result-summary">
                {Object.entries(result).map(([k, v]) => `${k}: ${v}`).join(' · ')}
              </span>
            )}
          </div>
          <div className="pipeline-log" ref={logRef}>
            {logs.length === 0 && status === 'running' && (
              <span className="pipeline-log-placeholder">Đang khởi động...</span>
            )}
            {logs.map((line, i) => (
              <div key={i} className="pipeline-log-line">{line}</div>
            ))}
            {status === 'completed' && (
              <div className="pipeline-log-line pipeline-log-done">✓ Hoàn tất.</div>
            )}
            {status === 'failed' && (
              <div className="pipeline-log-line pipeline-log-error">✗ Thất bại.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function PipelinePage() {
  return (
    <div className="pipeline-page">
      <JobSection
        title="Lọc chất lượng"
        description="Xóa bài viết quá ngắn (< 200 ký tự), quá dài (> 50 000 ký tự) hoặc quá ít từ (< 20 khoảng trắng)."
        onStart={startFilter}
        pollFn={getFilterStatus}
      />
      <JobSection
        title="Chạy pipeline"
        description="Phân đoạn tất cả bài viết trong database thành câu (MedicalTextPipeline)."
        onStart={startPipeline}
        pollFn={getPipelineStatus}
      />
    </div>
  );
}
