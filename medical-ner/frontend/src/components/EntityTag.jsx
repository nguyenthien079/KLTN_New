import React from 'react';
import { ENTITY_CONFIG } from '../config/entityConfig';

const EntityTag = ({ type, text, confidence }) => {
  const config = ENTITY_CONFIG[type] || {
    bg: '#f1f5f9',
    border: '#94a3b8',
    text: '#334155',
    label: type
  };

  const pct = confidence != null ? `${(confidence * 100).toFixed(1)}%` : null;

  return (
    <span
      className="entity-tag"
      style={{
        backgroundColor: config.bg,
        borderColor: config.border,
        color: config.text
      }}
      title={pct ? `${config.label} · Độ tin cậy: ${pct}` : config.label}
    >
      {text}
      <span className="entity-tag-label">{config.label}</span>
    </span>
  );
};

export default EntityTag;
