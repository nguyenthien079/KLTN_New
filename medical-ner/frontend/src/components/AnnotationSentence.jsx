import { useState } from 'react';
import EntityPopup from './EntityPopup';
import { ENTITY_CONFIG } from '../config/entityConfig';
import { expandToWordBoundaries } from '../utils/textSelection';
import './AnnotationSentence.css';

const AnnotationSentence = ({ sentence, entities, onEntitiesChange }) => {
  const [localEntities, setLocalEntities] = useState([...entities]);
  const [popup, setPopup] = useState(null);
  // popup = { mode, entityIdx?, start?, end?, text?, x, y }

  // Handler: Click existing entity to edit
  const handleEntityClick = (idx, e) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setPopup({
      mode: 'edit',
      entityIdx: idx,
      x: rect.left,
      y: rect.bottom + 6
    });
  };

  // Handler: Select new text to add entity
  const handleMouseUp = () => {
    const sel = window.getSelection();
    const text = sel?.toString().trim();
    if (!text || text.length === 0) return;

    // Find position in sentence (first occurrence of trimmed text)
    const trimmedStart = sentence.indexOf(text);
    if (trimmedStart === -1) {
      sel.removeAllRanges();
      return;
    }
    const trimmedEnd = trimmedStart + text.length;

    // Expand to word boundaries
    const { newStart: start, newEnd: end } = expandToWordBoundaries(sentence, trimmedStart, trimmedEnd);
    const expandedText = sentence.slice(start, end);

    // Check for overlap with existing entities
    const hasOverlap = localEntities.some(
      e => !(end <= e.start || start >= e.end)
    );
    if (hasOverlap) {
      sel.removeAllRanges();
      return;
    }

    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    setPopup({
      mode: 'add',
      start,
      end,
      text: expandedText,
      x: rect.left,
      y: rect.bottom + 6
    });

    sel.removeAllRanges();
  };

  // Handler: Popup select type
  const handlePopupSelect = (type) => {
    let updated;

    if (popup.mode === 'edit') {
      // Edit existing entity
      updated = localEntities.map((e, i) =>
        i === popup.entityIdx ? { ...e, type } : e
      );
    } else {
      // Add new entity
      updated = [
        ...localEntities,
        {
          text: popup.text,
          type,
          start: popup.start,
          end: popup.end,
          confidence: 1.0,
          source: 'human'
        }
      ].sort((a, b) => a.start - b.start);
    }

    setLocalEntities(updated);
    onEntitiesChange(updated);
    setPopup(null);
  };

  // Handler: Delete entity
  const handleDelete = () => {
    const updated = localEntities.filter((_, i) => i !== popup.entityIdx);
    setLocalEntities(updated);
    onEntitiesChange(updated);
    setPopup(null);
  };

  // Render sentence with highlighted entities
  const renderSentence = () => {
    const sorted = [...localEntities].sort((a, b) => a.start - b.start);
    const parts = [];
    let cursor = 0;

    sorted.forEach((entity, idx) => {
      // Add text before entity
      if (entity.start > cursor) {
        parts.push({
          kind: 'text',
          content: sentence.slice(cursor, entity.start)
        });
      }

      // Add entity
      parts.push({
        kind: 'entity',
        content: entity.text,
        entityType: entity.type,
        confidence: entity.confidence,
        entityIdx: idx
      });

      cursor = entity.end;
    });

    // Add remaining text
    if (cursor < sentence.length) {
      parts.push({
        kind: 'text',
        content: sentence.slice(cursor)
      });
    }

    return parts.map((part, idx) =>
      part.kind === 'text' ? (
        <span key={idx}>{part.content}</span>
      ) : (
        <AnnotationEntityTag
          key={idx}
          type={part.entityType}
          text={part.content}
          confidence={part.confidence}
          onClick={(e) => handleEntityClick(part.entityIdx, e)}
        />
      )
    );
  };

  return (
    <>
      <div className="annotation-sentence" onMouseUp={handleMouseUp}>
        {renderSentence()}
      </div>

      {popup && (
        <EntityPopup
          mode={popup.mode}
          currentType={popup.mode === 'edit' ? localEntities[popup.entityIdx]?.type : null}
          position={{ x: popup.x, y: popup.y }}
          onSelect={handlePopupSelect}
          onDelete={handleDelete}
          onClose={() => setPopup(null)}
        />
      )}
    </>
  );
};

// Clickable entity tag for annotation mode
const AnnotationEntityTag = ({ type, text, confidence, onClick }) => {
  const config = ENTITY_CONFIG[type] || {
    bg: '#f1f5f9',
    border: '#94a3b8',
    text: '#334155',
    label: type
  };

  const pct = confidence != null ? `${(confidence * 100).toFixed(1)}%` : null;

  return (
    <span
      className="annotation-entity-tag"
      style={{
        backgroundColor: config.bg,
        borderColor: config.border,
        color: config.text
      }}
      title={pct ? `${config.label} · Độ tin cậy: ${pct} · Click để sửa` : `${config.label} · Click để sửa`}
      onClick={onClick}
    >
      {text}
      <span className="annotation-entity-label">{config.label}</span>
    </span>
  );
};

export default AnnotationSentence;
