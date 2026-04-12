import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getLabelingArticle, getArticleSubmissions, saveSubmission } from '../services/api';
import { ENTITY_COLORS } from '../config/entityColors';
import './AnnotationView.css';

const ENTITY_TYPES = Object.keys(ENTITY_COLORS);

// ── Helper: render text with annotation highlights ─────────────────────────
function AnnotatedText({ text, myAnnotations, othersAnnotations, onRemove }) {
  // Build segments from offsets
  // Collect all boundaries, sort, slice text
  const events = [];
  myAnnotations.forEach((ann, idx) => {
    events.push({ pos: ann.start_offset, type: 'open', kind: 'mine', idx, ann });
    events.push({ pos: ann.end_offset, type: 'close', kind: 'mine', idx });
  });
  othersAnnotations.forEach((ann, idx) => {
    events.push({ pos: ann.start_offset, type: 'open', kind: 'other', idx, ann });
    events.push({ pos: ann.end_offset, type: 'close', kind: 'other', idx });
  });

  // Simple segment-based render: split text at all event positions
  const positions = [...new Set([0, ...events.map((e) => e.pos), text.length])].sort(
    (a, b) => a - b
  );

  const segments = [];
  for (let i = 0; i < positions.length - 1; i++) {
    const start = positions[i];
    const end = positions[i + 1];
    if (start >= end) continue;

    const chunk = text.slice(start, end);

    // Find any open mine annotation covering this segment
    const mineAnn = myAnnotations.find(
      (a) => a.start_offset <= start && a.end_offset >= end
    );
    // Find any open other annotation covering this segment
    const otherAnn = othersAnnotations.find(
      (a) => a.start_offset <= start && a.end_offset >= end
    );

    if (mineAnn) {
      const color = ENTITY_COLORS[mineAnn.entity_type];
      const mineIdx = myAnnotations.indexOf(mineAnn);
      segments.push(
        <mark
          key={`${start}-mine`}
          className="av-span-mine"
          style={{
            background: color?.bg || '#fef9c3',
            borderBottomColor: color?.border || '#ca8a04',
            color: color?.text || 'inherit',
          }}
          title={`${mineAnn.entity_type}${mineAnn.comment ? ' — ' + mineAnn.comment : ''} (click để xóa)`}
          onClick={() => onRemove(mineIdx)}
        >
          {chunk}
        </mark>
      );
    } else if (otherAnn) {
      const color = ENTITY_COLORS[otherAnn.entity_type];
      segments.push(
        <mark
          key={`${start}-other`}
          className="av-span-other"
          style={{
            background: color?.bg || '#f0f9ff',
            borderBottomColor: color?.border || '#7dd3fc',
          }}
          title={`${otherAnn.labeler_name}: ${otherAnn.entity_type}${otherAnn.comment ? ' — ' + otherAnn.comment : ''}`}
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

// ── Entity picker popup ────────────────────────────────────────────────────
function EntityPopup({ popup, onConfirm, onCancel }) {
  const [comment, setComment] = useState('');

  return (
    <div
      className="av-popup"
      style={{ top: popup.y, left: Math.min(popup.x, window.innerWidth - 260) }}
    >
      <div className="av-popup-title">"{popup.text}"</div>
      <div className="av-popup-types">
        {ENTITY_TYPES.map((type) => {
          const color = ENTITY_COLORS[type];
          return (
            <button
              key={type}
              className="av-type-btn"
              style={{ borderColor: color?.border, color: color?.text, background: color?.bg }}
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
        <button className="av-popup-cancel" onClick={onCancel}>Hủy</button>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
export default function AnnotationView({ articleId, onBack }) {
  const { user } = useAuth();
  const [article, setArticle] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [myAnnotations, setMyAnnotations] = useState([]);
  const [popup, setPopup] = useState(null); // {x, y, start, end, text}
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);
  const textRef = useRef(null);

  useEffect(() => {
    Promise.all([
      getLabelingArticle(articleId),
      getArticleSubmissions(articleId),
    ]).then(([art, subs]) => {
      setArticle(art);
      setSubmissions(subs);
      // load own draft annotations
      const mine = subs.find((s) => s.labeler_id === user.user_id);
      if (mine) setMyAnnotations(mine.annotations);
    });
  }, [articleId, user.user_id]);

  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;
    if (!textRef.current?.contains(sel.anchorNode)) return;

    const range = sel.getRangeAt(0);
    const text = sel.toString().trim();
    if (!text) return;

    // Calculate char offsets relative to clean_text
    const beforeRange = document.createRange();
    beforeRange.setStart(textRef.current, 0);
    beforeRange.setEnd(range.startContainer, range.startOffset);
    const start = beforeRange.toString().length;
    const end = start + text.length;

    const rect = range.getBoundingClientRect();
    setPopup({ x: rect.left + window.scrollX, y: rect.bottom + window.scrollY + 8, start, end, text });
    sel.removeAllRanges();
  }, []);

  const handleAddAnnotation = (entityType, comment) => {
    if (!popup) return;
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
    setPopup(null);
  };

  const handleRemoveAnnotation = (idx) => {
    setMyAnnotations((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSave = async (submit = false) => {
    setSaving(true);
    try {
      await saveSubmission(articleId, myAnnotations, submit);
      setSaveMsg(submit ? 'Đã nộp!' : 'Đã lưu nháp.');
      setTimeout(() => setSaveMsg(null), 2000);
      if (submit) {
        const subs = await getArticleSubmissions(articleId);
        setSubmissions(subs);
      }
    } catch {
      setSaveMsg('Lỗi lưu.');
    } finally {
      setSaving(false);
    }
  };

  if (!article) return <div className="av-loading">Đang tải...</div>;

  const othersAnnotations = submissions
    .filter((s) => s.labeler_id !== user.user_id)
    .flatMap((s) => s.annotations.map((a) => ({ ...a, labeler_name: s.labeler_name })));

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
            myAnnotations={myAnnotations}
            othersAnnotations={othersAnnotations}
            onRemove={handleRemoveAnnotation}
          />
        </div>
      </div>

      {popup && (
        <EntityPopup
          popup={popup}
          onConfirm={handleAddAnnotation}
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
        </div>
      </div>
    </div>
  );
}
