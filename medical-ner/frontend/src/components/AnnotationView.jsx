import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getLabelingArticle, getArticleSubmissions, saveSubmission, exportArticleAnnotations } from '../services/api';
import { ENTITY_COLORS } from '../config/entityColors';
import './AnnotationView.css';

const ENTITY_TYPES = Object.keys(ENTITY_COLORS);

// ── Helper: render text with annotation highlights ─────────────────────────
function AnnotatedText({ text, annotations, onEdit }) {
  const positions = [...new Set([0, ...annotations.flatMap((a) => [a.start_offset, a.end_offset]), text.length])].sort(
    (a, b) => a - b
  );

  const segments = [];
  for (let i = 0; i < positions.length - 1; i++) {
    const start = positions[i];
    const end = positions[i + 1];
    if (start >= end) continue;

    const chunk = text.slice(start, end);
    const ann = annotations.find((a) => a.start_offset <= start && a.end_offset >= end);

    if (ann) {
      const color = ENTITY_COLORS[ann.entity_type];
      const idx = annotations.indexOf(ann);
      segments.push(
        <mark
          key={`${start}-mine`}
          className="av-span-mine"
          style={{
            background: color?.bg || '#fef9c3',
            borderBottomColor: color?.border || '#ca8a04',
            color: color?.text || 'inherit',
          }}
          title={`${ann.entity_type}${ann.comment ? ' — ' + ann.comment : ''} (click để sửa)`}
          onClick={() => onEdit(idx)}
        >
          {chunk}
        </mark>
      );
    } else {
      segments.push(<span key={start}>{chunk}</span>);
    }
  }

  return <>{segments}</>;
}

// ── Entity picker / editor popup ──────────────────────────────────────────
function EntityPopup({ popup, onConfirm, onDelete, onCancel }) {
  const [comment, setComment] = useState(popup.comment || '');
  const isEdit = popup.mode === 'edit';

  useEffect(() => {
    setComment(popup.comment || '');
  }, [popup]);

  return (
    <div
      className="av-popup"
      style={{ top: popup.y, left: Math.min(popup.x, window.innerWidth - 260) }}
    >
      <div className="av-popup-title">"{popup.text}"</div>
      <div className="av-popup-types">
        {ENTITY_TYPES.map((type) => {
          const color = ENTITY_COLORS[type];
          const isActive = isEdit && type === popup.currentType;
          return (
            <button
              key={type}
              className={`av-type-btn${isActive ? ' av-type-btn--active' : ''}`}
              style={{ borderColor: color?.border, color: color?.text, background: isActive ? color?.border : color?.bg }}
              onClick={() => onConfirm(type, comment)}
            >
              {color?.label || type}
            </button>
          );
        })}
      </div>
      <textarea
        className="av-popup-comment"
        placeholder="Ghi chú (không bắt buộc)"
        rows={2}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <div className="av-popup-actions">
        {isEdit && (
          <button className="av-popup-delete" onClick={onDelete}>Xóa</button>
        )}
        <button className="av-popup-cancel" onClick={onCancel}>Hủy</button>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AnnotationView({ articleId, onBack }) {
  const { user } = useAuth();
  const canReview = user.role === 'chuyen_gia' || user.role === 'admin';
  const [article, setArticle] = useState(null);
  const [myAnnotations, setMyAnnotations] = useState([]);
  const [popup, setPopup] = useState(null); // {mode:'add'|'edit', x, y, start, end, text, currentType?, comment?, editIdx?}
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);
  const [fetchError, setFetchError] = useState(null);
  const textRef = useRef(null);

  useEffect(() => {
    Promise.all([
      getLabelingArticle(articleId),
      getArticleSubmissions(articleId),
    ]).then(([art, subs]) => {
      setArticle(art);
      const mine = subs.find((s) => s.labeler_id === user.user_id);
      if (mine) setMyAnnotations(mine.annotations);
    }).catch(() => {
      setFetchError('Không thể tải bài viết.');
    });
  }, [articleId, user.user_id]);

  // U3 fix: check both anchorNode and focusNode; trim-aware offsets
  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;
    if (
      !textRef.current?.contains(sel.anchorNode) ||
      !textRef.current?.contains(sel.focusNode)
    ) return;

    const range = sel.getRangeAt(0);
    const rawText = range.toString();
    const text = rawText.trim();
    if (!text) return;

    const beforeRange = document.createRange();
    beforeRange.setStart(textRef.current, 0);
    beforeRange.setEnd(range.startContainer, range.startOffset);

    const rawStart = beforeRange.toString().length;
    const leadingSpaces = rawText.length - rawText.trimStart().length;
    const start = rawStart + leadingSpaces;
    const end = start + text.length;

    const rect = range.getBoundingClientRect();
    setPopup({ mode: 'add', x: rect.left, y: rect.bottom + 8, start, end, text });
    sel.removeAllRanges();
  }, []);

  const handleEditClick = (idx) => {
    const ann = myAnnotations[idx];
    setPopup({
      mode: 'edit',
      x: 100,
      y: 80,
      start: ann.start_offset,
      end: ann.end_offset,
      text: ann.surface_text || '',
      currentType: ann.entity_type,
      comment: ann.comment || '',
      editIdx: idx,
    });
  };

  const handleConfirm = (entityType, comment) => {
    if (!popup) return;
    if (popup.mode === 'edit') {
      setMyAnnotations((prev) =>
        prev.map((ann, i) =>
          i === popup.editIdx
            ? { ...ann, entity_type: entityType, comment: comment || null }
            : ann
        )
      );
    } else {
      setMyAnnotations((prev) => [
        ...prev,
        {
          entity_type: entityType,
          start_offset: popup.start,
          end_offset: popup.end,
          surface_text: popup.text,
          comment: comment || null,
        },
      ]);
    }
    setPopup(null);
  };

  const handleDeleteAnnotation = () => {
    if (!popup || popup.editIdx == null) return;
    setMyAnnotations((prev) => prev.filter((_, i) => i !== popup.editIdx));
    setPopup(null);
  };

  const handleSave = async (submit = false) => {
    setSaving(true);
    try {
      await saveSubmission(articleId, myAnnotations, submit);
      setSaveMsg(submit ? 'Đã nộp!' : 'Đã lưu nháp.');
      setTimeout(() => setSaveMsg(null), 2000);
    } catch {
      setSaveMsg('Lỗi lưu.');
      setTimeout(() => setSaveMsg(null), 2000);
    } finally {
      setSaving(false);
    }
  };

  const handleCompleteReview = async () => {
    setSaving(true);
    try {
      await saveSubmission(articleId, myAnnotations, true);

      const jsonResp = await exportArticleAnnotations(articleId, 'json');
      downloadBlob(jsonResp.data, `article_${articleId}_annotations.json`);

      const csvResp = await exportArticleAnnotations(articleId, 'csv');
      downloadBlob(csvResp.data, `article_${articleId}_annotations.csv`);

      setSaveMsg('Đã hoàn thành review. Đang tải xuống file...');
      setTimeout(() => setSaveMsg(null), 3000);
    } catch {
      setSaveMsg('Lỗi khi hoàn thành review.');
      setTimeout(() => setSaveMsg(null), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (fetchError) return <div className="av-loading">{fetchError}</div>;
  if (!article) return <div className="av-loading">Đang tải...</div>;

  return (
    <div className="av-page">
      <div className="av-topbar">
        <button className="av-back-btn" onClick={onBack}>← Quay lại</button>
        <h2 className="av-article-title">{article.title || article.url}</h2>
      </div>

      <div className="av-text-wrap" onMouseUp={handleMouseUp}>
        <div ref={textRef} className="av-text-content">
          <AnnotatedText
            text={article.clean_text}
            annotations={myAnnotations}
            onEdit={handleEditClick}
          />
        </div>
      </div>

      {popup && (
        <EntityPopup
          popup={popup}
          onConfirm={handleConfirm}
          onDelete={handleDeleteAnnotation}
          onCancel={() => setPopup(null)}
        />
      )}

      <div className="av-bottombar">
        <span className="av-user-info">{user.display_name || user.username}</span>
        {saveMsg && <span className="av-save-msg">{saveMsg}</span>}
        <div className="av-actions">
          <button className="av-btn av-btn--draft" onClick={() => handleSave(false)} disabled={saving}>
            Lưu nháp
          </button>
          <button className="av-btn av-btn--submit" onClick={() => handleSave(true)} disabled={saving}>
            Nộp
          </button>
          {canReview && (
            <button className="av-btn av-btn--review" onClick={handleCompleteReview} disabled={saving}>
              Hoàn thành review
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
