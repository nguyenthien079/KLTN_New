import React from 'react';
import EntityTag from './EntityTag';

const HighlightedSentence = ({ sentence, entities }) => {
  const sorted = [...entities].sort((a, b) => a.start - b.start);

  const parts = [];
  let cursor = 0;

  for (const entity of sorted) {
    if (entity.start > cursor) {
      parts.push({ kind: 'text', content: sentence.slice(cursor, entity.start) });
    }
    parts.push({
      kind: 'entity',
      content: entity.text,
      entityType: entity.type,
      confidence: entity.confidence
    });
    cursor = entity.end;
  }

  if (cursor < sentence.length) {
    parts.push({ kind: 'text', content: sentence.slice(cursor) });
  }

  return (
    <p className="highlighted-sentence">
      {parts.map((part, idx) =>
        part.kind === 'text' ? (
          <span key={idx}>{part.content}</span>
        ) : (
          <EntityTag
            key={idx}
            type={part.entityType}
            text={part.content}
            confidence={part.confidence}
          />
        )
      )}
    </p>
  );
};

export default HighlightedSentence;
