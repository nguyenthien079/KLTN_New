import React from 'react';
import { ENTITY_COLORS } from '../config/entityColors';

const EntityTag = ({ type, text, confidence }) => {
  const colors = ENTITY_COLORS[type] || {
    bg: '#f3f4f6',
    border: '#9ca3af',
    text: '#374151',
    label: type
  };

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        margin: '0 4px',
        backgroundColor: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: '4px',
        color: colors.text,
        fontSize: '14px',
        fontWeight: '600',
        cursor: 'help',
      }}
      title={`${colors.label} - Confidence: ${(confidence * 100).toFixed(1)}%`}
    >
      {text}
      <span style={{ fontSize: '11px', marginLeft: '4px', opacity: 0.7 }}>
        ({colors.label})
      </span>
    </span>
  );
};

export default EntityTag;
