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

export default function LabelingPage() {
  const { user } = useAuth();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState([]);
  const [openedIds, setOpenedIds] = useState([]);
  const [articleDetails, setArticleDetails] = useState({});
  const [annotationsByArticle, setAnnotationsByArticle] = useState({});
  const [popup, setPopup] = useState(null); // {articleId, x, y, start, end, text}
  const [saveMsg, setSaveMsg] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getLabelingArticles()
      .then(setArticles)
      .catch(() => setArticles([]))
      .finally(() => setLoading(false));
  }, []);

  const toggleArticleSelection = (articleId) => {
    setSelectedIds((prev) =>
      prev.includes(articleId) ? prev.filter((id) => id !== articleId) : [...prev, articleId]
    );
  };

  const selectAll = () => {
    setSelectedIds(articles.map((a) => a.article_id));
  };

  const clearSelection = () => {
    setSelectedIds([]);
  };

  const openSelectedArticles = async () => {
    if (selectedIds.length === 0) {
      setSaveMsg('Hãy chọn ít nhất 1 bài để bắt đầu gán nhãn.');
      setTimeout(() => setSaveMsg(null), 2000);
      return;
    }

    setSaving(true);
    try {
      const payloads = await Promise.all(
        selectedIds.map(async (articleId) => {
          const [detail, submissions] = await Promise.all([
            getLabelingArticle(articleId),
            getArticleSubmissions(articleId),
          ]);
          const mine = submissions.find((s) => s.labeler_id === user.user_id);
          return {
            articleId,
            detail,
            mineAnnotations: mine?.annotations || [],
          };
        })
      );

      const detailsMap = {};
      const annotationsMap = {};
      payloads.forEach((item) => {
        detailsMap[item.articleId] = item.detail;
        annotationsMap[item.articleId] = item.mineAnnotations;
      });

      setArticleDetails((prev) => ({ ...prev, ...detailsMap }));
      setAnnotationsByArticle((prev) => ({ ...prev, ...annotationsMap }));
      setOpenedIds(selectedIds);
      setSaveMsg(`Đã mở ${selectedIds.length} bài để gán nhãn.`);
      setTimeout(() => setSaveMsg(null), 2000);
    } catch {
      setSaveMsg('Không thể tải một số bài đã chọn.');
      setTimeout(() => setSaveMsg(null), 2000);
    } finally {
      setSaving(false);
    }
  };

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

  const saveAll = async (submit = false) => {
    if (openedIds.length === 0) return;
    setSaving(true);
    try {
      await Promise.all(
        openedIds.map((articleId) =>
          saveSubmission(articleId, annotationsByArticle[articleId] || [], submit)
        )
      );
      setSaveMsg(submit ? 'Đã nộp toàn bộ bài đã mở.' : 'Đã lưu nháp toàn bộ bài đã mở.');
      setTimeout(() => setSaveMsg(null), 2200);
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

  const groupedTags = useMemo(() => {
    const grouped = {};
    ENTITY_TYPES.forEach((type) => {
      grouped[type] = [];
    });

    openedIds.forEach((articleId) => {
      const article = articleDetails[articleId];
      const anns = annotationsByArticle[articleId] || [];
      anns.forEach((ann) => {
        if (!grouped[ann.entity_type]) grouped[ann.entity_type] = [];
        grouped[ann.entity_type].push({
          articleTitle: article?.title || article?.url || `Bài ${articleId}`,
          text: ann.surface_text || '',
          start: ann.start_offset,
          end: ann.end_offset,
        });
      });
    });
    return grouped;
  }, [articleDetails, annotationsByArticle, openedIds]);

  return (
    <div className="labeling-page">
      <div className="labeling-header">
        <h2 className="labeling-title">Danh sách bài cần gán nhãn</h2>
        <span className="labeling-count">{articles.length} bài</span>
        <div className="labeling-actions-inline">
          <button className="labeling-btn labeling-btn--ghost" onClick={selectAll} disabled={loading || articles.length === 0}>Chọn tất cả</button>
          <button className="labeling-btn labeling-btn--ghost" onClick={clearSelection} disabled={selectedIds.length === 0}>Bỏ chọn</button>
          <button className="labeling-btn" onClick={openSelectedArticles} disabled={saving || selectedIds.length === 0}>Mở bài đã chọn</button>
        </div>
      </div>

      {loading && <p className="labeling-loading">Đang tải...</p>}
      {saveMsg && <p className="labeling-toast">{saveMsg}</p>}

      <div className="labeling-workspace">
        <div className="labeling-column labeling-column--left">
          <div className="labeling-table-wrap">
            <table className="labeling-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Tiêu đề / URL</th>
                  <th>Labelers</th>
                  <th>Trạng thái của bạn</th>
                </tr>
              </thead>
              <tbody>
                {articles.map((a) => {
                  const checked = selectedIds.includes(a.article_id);
                  return (
                    <tr key={a.article_id} className={checked ? 'labeling-row--selected' : ''}>
                      <td className="labeling-checkbox-cell">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleArticleSelection(a.article_id)}
                        />
                      </td>
                      <td className="labeling-title-cell">
                        {a.assigned_to_me && (
                          <span className="labeling-assigned-badge">Được assign</span>
                        )}
                        <span className="labeling-article-title">
                          {a.title || a.url}
                        </span>
                      </td>
                      <td className="labeling-count-cell">{a.submission_count}</td>
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
          </div>
        </div>

        <div className="labeling-column labeling-column--middle">
          <div className="labeling-batch-toolbar">
            <span>{openedIds.length} bài đang mở</span>
            <div>
              <button className="labeling-btn labeling-btn--ghost" onClick={() => saveAll(false)} disabled={saving || openedIds.length === 0}>Lưu nháp tất cả</button>
              <button className="labeling-btn" onClick={() => saveAll(true)} disabled={saving || openedIds.length === 0}>Nộp tất cả</button>
            </div>
          </div>
          <div className="labeling-articles-scroll">
            {openedIds.length === 0 && (
              <div className="labeling-empty-panel">Chọn nhiều bài bên trái rồi bấm "Mở bài đã chọn" để bắt đầu gán nhãn.</div>
            )}
            {openedIds.map((articleId) => {
              const detail = articleDetails[articleId];
              if (!detail) return null;
              return (
                <ArticleAnnotatorCard
                  key={articleId}
                  article={detail}
                  annotations={annotationsByArticle[articleId] || []}
                  onSelectText={handleSelectText}
                  onRemoveAnnotation={(idx) => removeAnnotation(articleId, idx)}
                />
              );
            })}
          </div>
        </div>

        <div className="labeling-column labeling-column--right">
          <h3 className="labeling-side-title">Danh sách đã gắn tag</h3>
          <div className="labeling-tag-groups">
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
                      <span className="labeling-tag-item-meta">{item.articleTitle} ({item.start}-{item.end})</span>
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
