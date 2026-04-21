import React, { useState, useEffect } from 'react';
import { getReviewQueue, confirmCorrection, rejectCorrection } from '../services/api';
import './ReviewPage.css';

const STATUS_LABEL = {
  pending_review: 'Chờ duyệt',
  confirmed: 'Đã duyệt',
  rejected: 'Từ chối',
};

function normalizeEntity(entity) {
  const start = Number.isInteger(entity.start) ? entity.start : entity.start_offset;
  const end = Number.isInteger(entity.end) ? entity.end : entity.end_offset;
  return {
    text: entity.text || entity.surface_text || '',
    type: entity.type || entity.entity_type || 'ENTITY',
    start,
    end,
  };
}

function renderHighlightedText(text, entities) {
  if (!text) return null;

  const normalized = (entities || [])
    .map(normalizeEntity)
    .filter((e) => Number.isInteger(e.start) && Number.isInteger(e.end) && e.start >= 0 && e.end > e.start)
    .sort((a, b) => a.start - b.start || a.end - b.end);

  if (normalized.length === 0) {
    return <span>{text}</span>;
  }

  const parts = [];
  let cursor = 0;

  normalized.forEach((entity, idx) => {
    const start = Math.min(entity.start, text.length);
    const end = Math.min(entity.end, text.length);

    if (start < cursor || end <= start) {
      return;
    }

    if (cursor < start) {
      parts.push(
        <span key={`plain-${idx}-${cursor}`}>{text.slice(cursor, start)}</span>
      );
    }

    const surface = text.slice(start, end);
    parts.push(
      <mark
        key={`mark-${idx}-${start}`}
        className="review-highlight"
        title={`${entity.type}${entity.text ? `: ${entity.text}` : ''}`}
      >
        {surface}
      </mark>
    );

    cursor = end;
  });

  if (cursor < text.length) {
    parts.push(<span key={`plain-tail-${cursor}`}>{text.slice(cursor)}</span>);
  }

  return parts;
}

export default function ReviewPage({ readOnly = false }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [selectedLabelers, setSelectedLabelers] = useState([]);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getReviewQueue();
      setItems(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleConfirm = async (id) => {
    setActionError(null);
    try {
      await confirmCorrection(id);
      setItems((prev) => prev.map((x) => x.id === id ? { ...x, status: 'confirmed' } : x));
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Không thể duyệt.');
    }
  };

  const handleReject = async (id) => {
    setActionError(null);
    try {
      await rejectCorrection(id);
      setItems((prev) => prev.map((x) => x.id === id ? { ...x, status: 'rejected' } : x));
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Không thể từ chối.');
    }
  };

  if (loading) return <div className="review-loading">Đang tải...</div>;
  if (error) return <div className="review-error">{error}</div>;

  // Get unique labelers
  const allLabelers = [...new Set(items.map((x) => x.labeler_id).filter(Boolean))].sort();

  // Filter items based on selected labelers
  const filteredItems =
    selectedLabelers.length === 0 ? items : items.filter((x) => selectedLabelers.includes(x.labeler_id));

  const pending = filteredItems.filter((x) => x.status === 'pending_review');
  const done = filteredItems.filter((x) => x.status !== 'pending_review');

  return (
    <div className="review-page">
      <div className="review-summary">
        <span className="review-count">{pending.length} chờ duyệt</span>
        <span className="review-count-done">{done.length} đã xử lý</span>
        {readOnly && <span className="review-count-done">Chế độ chỉ xem</span>}
        <button className="review-refresh-btn" onClick={load}>Làm mới</button>
      </div>

      {/* Labeler filter */}
      {allLabelers.length > 0 && (
        <div className="review-filter">
          <label className="review-filter-label">Lọc theo chuyên gia:</label>
          <div className="review-filter-items">
            {allLabelers.map((labeler) => (
              <label key={labeler} className="review-filter-checkbox">
                <input
                  type="checkbox"
                  checked={selectedLabelers.includes(labeler)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedLabelers((prev) => [...prev, labeler]);
                    } else {
                      setSelectedLabelers((prev) => prev.filter((id) => id !== labeler));
                    }
                  }}
                />
                <span>{labeler}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {actionError && <p className="review-error">{actionError}</p>}

      {filteredItems.length === 0 && (
        <div className="review-empty">Chưa có dữ liệu gán nhãn nào.</div>
      )}

      <div className="review-list">
        {filteredItems.map((item) => (
          <div key={item.id} className={`review-item review-item--${item.status}`}>
            <div className="review-item-header">
              <span className={`review-badge review-badge--${item.status}`}>
                {STATUS_LABEL[item.status] || item.status}
              </span>
              <span className="review-labeler">
                {item.labeler_id ? `Labeler: ${item.labeler_id}` : ''}
              </span>
            </div>

            {item.article_title && (
              <p className="review-text"><strong>Bài viết:</strong> {item.article_title}</p>
            )}

            <p className="review-text review-text--annotated">
              {renderHighlightedText(item.original_text, item.corrected_entities)}
            </p>

            <div className="review-entities">
              <div className="review-entities-col">
                <span className="review-entities-label">Gốc ({item.original_entities.length})</span>
                {item.original_entities.map((e, i) => (
                  <span key={i} className="review-entity-chip review-entity-chip--original">
                    {e.text} <em>{e.type}</em>
                  </span>
                ))}
              </div>
              <div className="review-entities-col">
                <span className="review-entities-label">Đã sửa ({item.corrected_entities.length})</span>
                {item.corrected_entities.map((e, i) => (
                  <span key={i} className="review-entity-chip review-entity-chip--corrected">
                    {e.text} <em>{e.type}</em>
                  </span>
                ))}
              </div>
            </div>

            {!readOnly && item.status === 'pending_review' && (
              <div className="review-actions">
                <button
                  className="review-btn review-btn--confirm"
                  onClick={() => handleConfirm(item.id)}
                >
                  Duyệt
                </button>
                <button
                  className="review-btn review-btn--reject"
                  onClick={() => handleReject(item.id)}
                >
                  Từ chối
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
