import React, { useEffect, useMemo, useState } from 'react';
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

function stringToHue(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) % 360;
  }
  return hash;
}

function keyFromOwners(owners) {
  return owners.slice().sort().join('|');
}

function userColorByIndex(index) {
  const hue = (index * 137.508) % 360;
  return {
    bg: `hsl(${hue} 82% 86%)`,
    border: `hsl(${hue} 78% 35%)`,
  };
}

function colorFromOwners(owners, labelerColorMap, comboColorMap) {
  if (!owners || owners.length === 0) {
    return { bg: 'transparent', border: 'transparent', isCombo: false };
  }

  if (owners.length === 1) {
    const base = labelerColorMap.get(owners[0]) || { bg: 'hsl(210 82% 86%)', border: 'hsl(210 78% 35%)' };
    return { bg: base.bg, border: base.border, isCombo: false };
  }

  const key = keyFromOwners(owners);
  const combo = comboColorMap.get(key);
  if (combo) {
    return { ...combo, isCombo: true };
  }

  const hue = stringToHue(key);
  return {
    bg: `repeating-linear-gradient(135deg, hsl(${hue} 92% 86%) 0 5px, hsl(${(hue + 120) % 360} 92% 80%) 5px 10px)`,
    border: `hsl(${hue} 75% 42%)`,
    isCombo: true,
  };
}

function buildSegments(text, entitiesByLabeler) {
  const boundaries = new Set([0, text.length]);
  const normalized = [];

  Object.entries(entitiesByLabeler || {}).forEach(([labelerId, entities]) => {
    (entities || []).forEach((entity) => {
      const n = normalizeEntity(entity);
      if (!Number.isInteger(n.start) || !Number.isInteger(n.end)) return;
      if (n.start < 0 || n.end <= n.start || n.end > text.length) return;
      boundaries.add(n.start);
      boundaries.add(n.end);
      normalized.push({ ...n, owner: labelerId });
    });
  });

  const points = Array.from(boundaries).sort((a, b) => a - b);
  const segments = [];

  for (let i = 0; i < points.length - 1; i += 1) {
    const start = points[i];
    const end = points[i + 1];
    if (end <= start) continue;

    const cover = normalized.filter((e) => e.start <= start && e.end >= end);
    const owners = Array.from(new Set(cover.map((x) => x.owner))).sort();
    const types = Array.from(new Set(cover.map((x) => x.type))).sort();
    segments.push({ start, end, text: text.slice(start, end), owners, types });
  }

  return segments;
}

function renderComparedText(text, entitiesByLabeler, labelerColorMap, comboColorMap) {
  if (!text) return null;
  const segments = buildSegments(text, entitiesByLabeler);

  return segments.map((seg, idx) => {
    if (seg.owners.length === 0) {
      return <span key={`seg-${idx}`}>{seg.text}</span>;
    }

    const c = colorFromOwners(seg.owners, labelerColorMap, comboColorMap);
    return (
      <mark
        key={`seg-${idx}`}
        className="review-highlight"
        style={{
          background: c.bg,
          borderBottomColor: c.border,
          borderBottomStyle: c.isCombo ? 'dashed' : 'solid',
        }}
        title={`Người gán: ${seg.owners.join(', ')}${seg.types.length ? ` | Tag: ${seg.types.join(', ')}` : ''}`}
      >
        {seg.text}
      </mark>
    );
  });
}

export default function ReviewPage({ readOnly = false }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [selectedArticleId, setSelectedArticleId] = useState(null);
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await getReviewQueue();
      const safeData = data || [];
      setItems(safeData);
      const articleIds = Array.from(new Set(safeData.map((x) => x.article_id))).sort((a, b) => a - b);
      setSelectedArticleId((prev) => (prev != null && articleIds.includes(prev) ? prev : articleIds[0] ?? null));
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
      setItems((prev) => prev.map((x) => (x.id === id ? { ...x, status: 'confirmed', reject_reason: null } : x)));
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Không thể duyệt.');
    }
  };

  const handleReject = async (id, reason) => {
    setActionError(null);
    try {
      const data = await rejectCorrection(id, reason);
      setItems((prev) => prev.map((x) => (x.id === id ? { ...x, status: 'rejected', reject_reason: data?.reject_reason || reason || null } : x)));
      setRejectingId(null);
      setRejectReason('');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Không thể từ chối.');
    }
  };
  const allLabelers = [...new Set(items.map((x) => x.labeler_id).filter(Boolean))].sort();
  const filteredItems = items;

  const labelerColorMap = useMemo(() => {
    const map = new Map();
    allLabelers.forEach((id, idx) => {
      map.set(id, userColorByIndex(idx));
    });
    return map;
  }, [allLabelers]);

  const comboColorMap = useMemo(() => {
    const map = new Map();
    const combos = new Set();

    const grouped = new Map();
    filteredItems.forEach((item) => {
      if (!grouped.has(item.article_id)) grouped.set(item.article_id, []);
      grouped.get(item.article_id).push(item);
    });

    grouped.forEach((subs) => {
      const entitiesByLabeler = {};
      const text = subs[0]?.original_text || '';
      subs.forEach((s) => {
        entitiesByLabeler[s.labeler_id || 'unknown'] = (s.corrected_entities || []).map(normalizeEntity);
      });
      buildSegments(text, entitiesByLabeler).forEach((seg) => {
        if (seg.owners.length > 1) combos.add(keyFromOwners(seg.owners));
      });
    });

    Array.from(combos).sort().forEach((key, idx) => {
      const hue = (idx * 97 + 35) % 360;
      map.set(key, {
        bg: `repeating-linear-gradient(135deg, hsl(${hue} 95% 88%) 0 5px, hsl(${(hue + 165) % 360} 95% 78%) 5px 10px)`,
        border: `hsl(${hue} 85% 32%)`,
      });
    });

    return map;
  }, [filteredItems]);

  const groups = useMemo(() => {
    const m = new Map();
    filteredItems.forEach((item) => {
      if (!m.has(item.article_id)) {
        m.set(item.article_id, {
          article_id: item.article_id,
          article_title: item.article_title,
          original_text: item.original_text || '',
          submissions: [],
        });
      }
      m.get(item.article_id).submissions.push(item);
    });

    return Array.from(m.values()).map((g) => {
      const entitiesByLabeler = {};
      let pending = 0;
      let done = 0;
      g.submissions.forEach((sub) => {
        if (sub.status === 'pending_review') pending += 1;
        else done += 1;
        entitiesByLabeler[sub.labeler_id || 'unknown'] = (sub.corrected_entities || []).map(normalizeEntity);
      });

      return {
        ...g,
        pending,
        done,
        entitiesByLabeler,
        labelers: Array.from(new Set(g.submissions.map((x) => x.labeler_id).filter(Boolean))).sort(),
      };
    }).sort((a, b) => {
      if (a.pending !== b.pending) return b.pending - a.pending;
      return a.article_id - b.article_id;
    });
  }, [filteredItems]);

  const pending = groups.reduce((s, x) => s + x.pending, 0);
  const done = groups.reduce((s, x) => s + x.done, 0);
  const activeGroup = groups.find((x) => x.article_id === selectedArticleId) || groups[0] || null;

  const overlapLegend = useMemo(() => {
    if (!activeGroup) return [];
    const keys = new Set();
    buildSegments(activeGroup.original_text, activeGroup.entitiesByLabeler).forEach((seg) => {
      if (seg.owners.length > 1) keys.add(keyFromOwners(seg.owners));
    });
    return Array.from(keys).sort();
  }, [activeGroup]);

  if (loading) return <div className="review-loading">Đang tải...</div>;
  if (error) return <div className="review-error">{error}</div>;

  return (
    <div className="review-page">
      <div className="review-summary">
        <span className="review-count">{pending.length} chờ duyệt</span>
        <span className="review-count-done">{done.length} đã xử lý</span>
        {readOnly && <span className="review-count-done">Chế độ chỉ xem</span>}
        <button className="review-refresh-btn" onClick={load}>Làm mới</button>
      </div>

      {actionError && <p className="review-error">{actionError}</p>}

      {groups.length === 0 && (
        <div className="review-empty">Chưa có dữ liệu gán nhãn nào.</div>
      )}

      {groups.length > 0 && (
        <div className="review-split">
          <aside className="review-left-pane">
            <div className="review-left-title">File cần duyệt</div>
            <div className="review-file-list">
              {groups.map((g) => (
                <button
                  key={g.article_id}
                  type="button"
                  className={`review-file-item${activeGroup?.article_id === g.article_id ? ' review-file-item--active' : ''}`}
                  onClick={() => setSelectedArticleId(g.article_id)}
                >
                  <div className="review-file-item-title">{g.article_title || `Bài ${g.article_id}`}</div>
                  <div className="review-file-item-meta">
                    <span>ID {g.article_id}</span>
                    <span>{g.pending} chờ duyệt</span>
                    <span>{g.labelers.length} người gán</span>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section className="review-right-pane">
            {activeGroup && (
              <>
                <div className="review-right-header">
                  <h3>{activeGroup.article_title || `Bài ${activeGroup.article_id}`}</h3>
                  <span>ID {activeGroup.article_id}</span>
                </div>

                <div className="review-legend-wrap">
                  <div className="review-legend-title">Chú thích màu theo người gán nhãn</div>
                  <div className="review-legend-list">
                    {activeGroup.labelers.map((labelerId) => {
                      const color = colorFromOwners([labelerId], labelerColorMap, comboColorMap);
                      return (
                        <span key={labelerId} className="review-legend-item">
                          <span className="review-legend-dot" style={{ background: color.bg, borderColor: color.border }} />
                          {labelerId}
                        </span>
                      );
                    })}
                    {overlapLegend.map((k) => {
                      const owners = k.split('|');
                      const color = colorFromOwners(owners, labelerColorMap, comboColorMap);
                      return (
                        <span key={k} className="review-legend-item review-legend-item--combo">
                          <span className="review-legend-dot" style={{ background: color.bg, borderColor: color.border }} />
                          Trùng: {owners.join(' + ')}
                        </span>
                      );
                    })}
                  </div>
                </div>

                <p className="review-text review-text--annotated review-text--compare">
                  {renderComparedText(activeGroup.original_text, activeGroup.entitiesByLabeler, labelerColorMap, comboColorMap)}
                </p>

                <div className="review-right-submissions">
                  {activeGroup.submissions.map((sub) => {
                    const labelerColor = colorFromOwners([sub.labeler_id || 'unknown'], labelerColorMap, comboColorMap);
                    return (
                      <div key={sub.id} className={`review-item review-item--${sub.status}`}>
                        <div className="review-item-header">
                          <span className={`review-badge review-badge--${sub.status}`}>
                            {STATUS_LABEL[sub.status] || sub.status}
                          </span>
                          <span className="review-labeler">{sub.labeler_id ? `Labeler: ${sub.labeler_id}` : ''}</span>
                        </div>

                        <div className="review-entities-col">
                          <span className="review-entities-label">Tag đã gán ({(sub.corrected_entities || []).length})</span>
                          <div className="review-entity-chip-wrap">
                            {(sub.corrected_entities || []).map((e, i) => {
                              const n = normalizeEntity(e);
                              return (
                                <span
                                  key={`${sub.id}-${i}`}
                                  className="review-entity-chip"
                                  style={{ background: labelerColor.bg, border: `1px solid ${labelerColor.border}` }}
                                >
                                  {n.text} <em>{n.type}</em>
                                </span>
                              );
                            })}
                          </div>
                        </div>

                        {sub.status === 'rejected' && sub.reject_reason && (
                          <div className="review-reject-reason">
                            <strong>Ly do tu choi:</strong> {sub.reject_reason}
                          </div>
                        )}

                        {!readOnly && sub.status === 'pending_review' && (
                          <div className="review-actions">
                            <button className="review-btn review-btn--confirm" onClick={() => handleConfirm(sub.id)}>
                              Duyệt
                            </button>
                            <button
                              className="review-btn review-btn--reject"
                              onClick={() => {
                                setRejectingId((prev) => (prev === sub.id ? null : sub.id));
                                setRejectReason('');
                              }}
                            >
                              Từ chối
                            </button>
                          </div>
                        )}

                        {!readOnly && sub.status === 'pending_review' && rejectingId === sub.id && (
                          <div className="review-reject-editor">
                            <label htmlFor={`reject-reason-${sub.id}`}>Ly do tu choi (gui cho chuyen gia)</label>
                            <textarea
                              id={`reject-reason-${sub.id}`}
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                              rows={2}
                              placeholder="Nhap ly do tu choi..."
                            />
                            <div className="review-reject-editor-actions">
                              <button className="review-btn review-btn--reject" onClick={() => handleReject(sub.id, rejectReason)}>
                                Xac nhan tu choi
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
