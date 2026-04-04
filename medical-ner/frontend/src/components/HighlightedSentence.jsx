import React from 'react';
import EntityTag from './EntityTag';

const HighlightedSentence = ({ sentence, entities }) => {
  const sortedEntities = [...entities].sort((a, b) => a.start - b.start);

  const parts = [];
  let lastIndex = 0;

  for (const entity of sortedEntities) {
    if (entity.start > lastIndex) {
      parts.push({ type: 'text', content: sentence.slice(lastIndex, entity.start) });
    }
    parts.push({
      type: 'entity',
      content: entity.text,
      entityType: entity.type,
      confidence: entity.confidence
    });
    lastIndex = entity.end;
  }

  if (lastIndex < sentence.length) {
    parts.push({ type: 'text', content: sentence.slice(lastIndex) });
  }

  return (
    <div style={{ marginBottom: '16px', lineHeight: '2' }}>
      {parts.map((part, idx) =>
        part.type === 'text' ? (
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
    </div>
  );
};

export default HighlightedSentence;
