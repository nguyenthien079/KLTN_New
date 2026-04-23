// frontend/src/components/LabelingPage.jsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getArticleSubmissions, getLabelingArticle, getLabelingArticles, saveSubmission } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { ENTITY_COLORS } from '../config/entityColors';
import './LabelingPage.css';

const ENTITY_TYPES = Object.keys(ENTITY_COLORS);

function EntityPopup({ popup, onConfirm, onCancel }) {
  const [comment, setComment] = useState('');

  useEffect(() => {
    setComment('');
  }, [popup]);

  if (!popup) return null;

  return (
    <div
      className="labeling-popup"
      style={{ top: popup.y, left: Math.min(popup.x, window.innerWidth - 280) }}
    >
      <div className="labeling-popup-title">"{popup.text}"</div>
      <div className="labeling-popup-types">
        {ENTITY_TYPES.map((type) => {
          const color = ENTITY_COLORS[type];
          return (
            <button
              key={type}
              className="labeling-popup-type-btn"
              style={{ borderColor: color?.border, color: color?.text, background: color?.bg }}
              onClick={() => onConfirm(type, comment)}
            >
              {color?.label || type}
            </button>
          );
        })}
      </div>
      <textarea
        className="labeling-popup-comment"
        placeholder="Ghi chú (không bắt buộc)"
        rows={2}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <div className="labeling-popup-actions">
        <button className="labeling-popup-cancel" onClick={onCancel}>Hủy</button>
      </div>
    </div>
  );
}

function AnnotatedText({ text, annotations, onRemove }) {
  const positions = [0, text.length];
  annotations.forEach((ann) => {
    positions.push(ann.start_offset, ann.end_offset);
  });
  const sortedPositions = [...new Set(positions)]
    .filter((n) => Number.isInteger(n) && n >= 0 && n <= text.length)
    .sort((a, b) => a - b);

  const segments = [];
  for (let i = 0; i < sortedPositions.length - 1; i++) {
    const start = sortedPositions[i];
    const end = sortedPositions[i + 1];
    if (start >= end) continue;

    const piece = text.slice(start, end);
    const annIndex = annotations.findIndex(
      (a) => a.start_offset <= start && a.end_offset >= end
    );

    if (annIndex >= 0) {
      const ann = annotations[annIndex];
      const color = ENTITY_COLORS[ann.entity_type];
      segments.push(
        <mark
          key={`${start}-${end}`}
          className="labeling-annotated-mark"
          style={{
            background: color?.bg || '#fef3c7',
            borderBottomColor: color?.border || '#f59e0b',
            color: color?.text || 'inherit',
          }}
          title={`${color?.label || ann.entity_type}${ann.comment ? ` - ${ann.comment}` : ''} (click để xóa)`}
          onClick={() => onRemove(annIndex)}
        >
          {piece}
        </mark>
      );
    } else {
      segments.push(<span key={`${start}-${end}`}>{piece}</span>);
    }
  }

  return <>{segments}</>;
}

function ArticleAnnotatorCard({ article, annotations, onSelectText, onRemoveAnnotation }) {
  const textRef = useRef(null);

  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;
    if (!textRef.current?.contains(sel.anchorNode) || !textRef.current?.contains(sel.focusNode)) return;

    const range = sel.getRangeAt(0);
    const rawText = range.toString();
    const trimmed = rawText.trim();
    if (!trimmed) return;

    const beforeRange = document.createRange();
    beforeRange.setStart(textRef.current, 0);
    beforeRange.setEnd(range.startContainer, range.startOffset);

    const start = beforeRange.toString().length;
    const end = start + rawText.length;
    const rect = range.getBoundingClientRect();
    onSelectText(article.article_id, { x: rect.left, y: rect.bottom + 8, start, end, text: trimmed });
    sel.removeAllRanges();
  }, [article.article_id, onSelectText]);

  return (
    <div className="labeling-article-card">
      <div className="labeling-article-card-header">
        <h4>{article.title || article.url}</h4>
      </div>
      <div className="labeling-article-text" onMouseUp={handleMouseUp}>
        <div ref={textRef} className="labeling-article-text-inner">
          <AnnotatedText text={article.clean_text || ''} annotations={annotations} onRemove={onRemoveAnnotation} />
        </div>
      </div>
    </div>
  );
}

export default function LabelingPage({ focusRequest = null }) {
  const { user } = useAuth();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedArticleId, setSelectedArticleId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [isStatusFilterOpen, setIsStatusFilterOpen] = useState(false);
  const [articleDetails, setArticleDetails] = useState({});
  const [annotationsByArticle, setAnnotationsByArticle] = useState({});
  const [popup, setPopup] = useState(null); // {articleId, x, y, start, end, text}
  const [saveMsg, setSaveMsg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loadingArticleId, setLoadingArticleId] = useState(null);
  const loadedArticleIdsRef = useRef(new Set());
  const statusFilterRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (statusFilterRef.current && !statusFilterRef.current.contains(event.target)) {
        setIsStatusFilterOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    getLabelingArticles()
      .then((data) => {
        setArticles(data || []);
        if (data?.length) {
          setSelectedArticleId((current) => current ?? data[0].article_id);
        }
      })
      .catch(() => {
        setArticles([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const loadArticle = useCallback(async (articleId) => {
    setSelectedArticleId(articleId);

    if (loadedArticleIdsRef.current.has(articleId)) {
      return;
    }

    setLoadingArticleId(articleId);
    try {
      const [detail, submissions] = await Promise.all([
        getLabelingArticle(articleId),
        getArticleSubmissions(articleId),
      ]);
      const mine = submissions.find((s) => s.labeler_id === user.user_id);

      setArticleDetails((prev) => ({
        ...prev,
        [articleId]: detail,
      }));
      setAnnotationsByArticle((prev) => ({
        ...prev,
        [articleId]: mine?.annotations || [],
      }));
      loadedArticleIdsRef.current.add(articleId);
    } catch {
      setSaveMsg('Không thể tải bài đã chọn.');
      setTimeout(() => setSaveMsg(null), 2000);
    } finally {
      setLoadingArticleId(null);
    }
  }, [user.user_id]);

  useEffect(() => {
    const focusArticleId = focusRequest?.articleId;
    if (focusArticleId == null) return;
    loadArticle(focusArticleId);
  }, [focusRequest, loadArticle]);

  useEffect(() => {
    if (selectedArticleId != null) {
      loadArticle(selectedArticleId);
    }
  }, [loadArticle, selectedArticleId]);

  const handleSelectText = (articleId, pos) => {
    setPopup({ articleId, ...pos });
  };

  const addAnnotation = (entityType, comment) => {
    if (!popup) return;
    const ann = {
      entity_type: entityType,
      start_offset: popup.start,
      end_offset: popup.end,
      surface_text: popup.text,
      comment: comment || null,
    };
    setAnnotationsByArticle((prev) => ({
      ...prev,
      [popup.articleId]: [...(prev[popup.articleId] || []), ann],
    }));
    setPopup(null);
  };

  const removeAnnotation = (articleId, index) => {
    setAnnotationsByArticle((prev) => ({
      ...prev,
      [articleId]: (prev[articleId] || []).filter((_, i) => i !== index),
    }));
  };

  const refreshArticles = () =>
    getLabelingArticles().then(setArticles).catch(() => {});

  const saveCurrent = async (submit = false) => {
    if (selectedArticleId == null) return;
    setSaving(true);
    try {
      await saveSubmission(selectedArticleId, annotationsByArticle[selectedArticleId] || [], submit);
      setSaveMsg(submit ? 'Đã nộp bài đang chọn.' : 'Đã lưu nháp bài đang chọn.');
      setTimeout(() => setSaveMsg(null), 2200);
      await refreshArticles();
    } catch {
      setSaveMsg('Lỗi khi lưu dữ liệu gán nhãn.');
      setTimeout(() => setSaveMsg(null), 2200);
    } finally {
      setSaving(false);
    }
  };

  const STATUS_LABEL = {
    draft: 'Đang làm',
    submitted: 'Đã nộp',
    confirmed: 'Đã duyệt',
    rejected: 'Bị từ chối',
  };

  const FILTER_OPTIONS = [
    { value: 'all', label: 'Tất cả' },
    { value: 'draft', label: 'Đang làm' },
    { value: 'none', label: 'Chưa làm' },
    { value: 'submitted', label: 'Đã nộp' },
    { value: 'rejected', label: 'Bị từ chối' },
    { value: 'confirmed', label: 'Đã duyệt' },
  ];

  const filteredSortedArticles = useMemo(() => {
    const getPriority = (status) => {
      if (status === 'draft') return 0;
      if (!status) return 1;
      if (status === 'submitted' || status === 'rejected' || status === 'confirmed') return 2;
      return 3;
    };

    return [...articles]
      .filter((a) => {
        if (statusFilter === 'all') return true;
        if (statusFilter === 'none') return !a.my_status;
        return a.my_status === statusFilter;
      })
      .sort((a, b) => {
      const byStatus = getPriority(a.my_status) - getPriority(b.my_status);
      if (byStatus !== 0) return byStatus;
      return a.article_id - b.article_id;
      });
  }, [articles, statusFilter]);

  useEffect(() => {
    if (filteredSortedArticles.length === 0) {
      setSelectedArticleId(null);
      return;
    }

    const stillVisible = filteredSortedArticles.some((a) => a.article_id === selectedArticleId);
    if (!stillVisible) {
      setSelectedArticleId(filteredSortedArticles[0].article_id);
    }
  }, [filteredSortedArticles, selectedArticleId]);

  const groupedTags = useMemo(() => {
    const grouped = {};
    ENTITY_TYPES.forEach((type) => {
      grouped[type] = [];
    });

    if (selectedArticleId != null) {
      const article = articleDetails[selectedArticleId];
      const articleText = article?.clean_text || '';
      const anns = annotationsByArticle[selectedArticleId] || [];
      anns.forEach((ann) => {
        if (!grouped[ann.entity_type]) grouped[ann.entity_type] = [];

        let displayText = ann.surface_text || '';
        if (
          Number.isInteger(ann.start_offset)
          && Number.isInteger(ann.end_offset)
          && ann.start_offset >= 0
          && ann.end_offset > ann.start_offset
          && ann.end_offset <= articleText.length
        ) {
          displayText = articleText.slice(ann.start_offset, ann.end_offset);
        }

        grouped[ann.entity_type].push({
          text: displayText,
          start: ann.start_offset,
          end: ann.end_offset,
        });
      });
    }
    return grouped;
  }, [articleDetails, annotationsByArticle, selectedArticleId]);

  const selectedArticle = selectedArticleId != null ? articleDetails[selectedArticleId] : null;
  const selectedAnnotations = selectedArticleId != null ? (annotationsByArticle[selectedArticleId] || []) : [];

  return (
    <div className="labeling-page">
      <div className="labeling-header">
        <h2 className="labeling-title">Danh sách bài cần gán nhãn</h2>
        <span className="labeling-count">{articles.length} bài</span>
        {loadingArticleId != null && <span className="labeling-loading">Đang tải bài được chọn...</span>}
      </div>

      {loading && <p className="labeling-loading">Đang tải...</p>}
      {saveMsg && <p className="labeling-toast">{saveMsg}</p>}

      <div className="labeling-workspace">
        <div className="labeling-column labeling-column--left">
          <div className="labeling-table-wrap">
            <table className={`labeling-table${filteredSortedArticles.length === 0 ? ' labeling-table--empty' : ''}`}>
              <thead>
                <tr>
                  <th>Tiêu đề / URL</th>
                  <th className="labeling-status-header-cell">
                    <div className="labeling-status-filter" ref={statusFilterRef}>
                      <button
                        type="button"
                        className="labeling-status-filter-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setIsStatusFilterOpen((prev) => !prev);
                        }}
                      >
                        Trạng thái của bạn
                        <span className="labeling-status-filter-value">
                          {FILTER_OPTIONS.find((opt) => opt.value === statusFilter)?.label || 'Tất cả'}
                        </span>
                      </button>
                      {isStatusFilterOpen && (
                        <div className="labeling-status-filter-menu">
                          {FILTER_OPTIONS.map((opt) => (
                            <button
                              key={opt.value}
                              type="button"
                              className={`labeling-status-filter-item${statusFilter === opt.value ? ' labeling-status-filter-item--active' : ''}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                setStatusFilter(opt.value);
                                setIsStatusFilterOpen(false);
                              }}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredSortedArticles.map((a) => {
                  const active = selectedArticleId === a.article_id;
                  return (
                    <tr
                      key={a.article_id}
                      className={active ? 'labeling-row--selected' : ''}
                      onClick={() => loadArticle(a.article_id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          loadArticle(a.article_id);
                        }
                      }}
                    >
                      <td className="labeling-title-cell">
                        {a.assigned_to_me && (
                          <span className="labeling-assigned-badge">Được assign</span>
                        )}
                        <span className="labeling-article-title">
                          {a.title || a.url}
                        </span>
                      </td>
                      <td>
                        {a.my_status ? (
                          <span className={`labeling-status labeling-status--${a.my_status}`}>
                            {STATUS_LABEL[a.my_status]}
                          </span>
                        ) : (
                          <span className="labeling-status labeling-status--none">Chưa làm</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredSortedArticles.length === 0 && (
              <div className="labeling-empty-filter-panel">
                Không có bài nào ở trạng thái đã chọn.
              </div>
            )}
          </div>
        </div>

        <div className="labeling-column labeling-column--middle">
          <div className="labeling-batch-toolbar">
            <span>{selectedArticleId != null ? `Bài đang chọn: ${selectedArticle?.title || selectedArticle?.url || `#${selectedArticleId}`}` : 'Chọn một bài bên trái để bắt đầu'}</span>
            <div>
              <button className="labeling-btn labeling-btn--ghost" onClick={() => saveCurrent(false)} disabled={saving || selectedArticleId == null}>Lưu nháp</button>
              <button className="labeling-btn" onClick={() => saveCurrent(true)} disabled={saving || selectedArticleId == null}>Nộp bài</button>
            </div>
          </div>
          <div className="labeling-articles-scroll">
            {selectedArticleId == null && (
              <div className="labeling-empty-panel">Chọn một bài ở danh sách bên trái để xem và gán nhãn.</div>
            )}
            {selectedArticleId != null && !selectedArticle && (
              <div className="labeling-empty-panel">Đang tải thông tin bài được chọn...</div>
            )}
            {selectedArticle && (
              <ArticleAnnotatorCard
                article={selectedArticle}
                annotations={selectedAnnotations}
                onSelectText={handleSelectText}
                onRemoveAnnotation={(idx) => removeAnnotation(selectedArticleId, idx)}
              />
            )}
          </div>
        </div>

        <div className="labeling-column labeling-column--right">
          <h3 className="labeling-side-title">Tag của bài đang chọn</h3>
          <div className="labeling-tag-groups">
            {selectedArticleId == null && (
              <p className="labeling-tag-empty labeling-tag-empty--center">Chọn một bài để xem tag.</p>
            )}
            {ENTITY_TYPES.map((type) => {
              const color = ENTITY_COLORS[type];
              const items = groupedTags[type] || [];
              return (
                <div key={type} className="labeling-tag-group">
                  <div className="labeling-tag-group-header" style={{ borderColor: color?.border }}>
                    <span style={{ color: color?.text }}>{color?.label || type}</span>
                    <strong>{items.length}</strong>
                  </div>
                  {items.length === 0 && <p className="labeling-tag-empty">Chưa có</p>}
                  {items.map((item, index) => (
                    <div key={`${type}-${index}`} className="labeling-tag-item">
                      <span className="labeling-tag-item-text">{item.text}</span>
                      <span className="labeling-tag-item-meta">({item.start}-{item.end})</span>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <EntityPopup
        popup={popup}
        onConfirm={addAnnotation}
        onCancel={() => setPopup(null)}
      />
    </div>
  );
}
