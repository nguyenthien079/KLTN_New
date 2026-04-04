import React from 'react';
import { ENTITY_CONFIG } from '../config/entityConfig';

const EntityDistribution = ({ byType }) => {
  const entries = Object.entries(byType).filter(([, count]) => count > 0);
  if (entries.length === 0) return null;

  const max = Math.max(...entries.map(([, c]) => c));

  return (
    <div className="entity-distribution">
      <h3 className="distribution-title">Phân bố thực thể</h3>
      <div className="distribution-bars">
        {entries
          .sort((a, b) => b[1] - a[1])
          .map(([type, count]) => {
            const config = ENTITY_CONFIG[type] || { border: '#94a3b8', label: type };
            const pct = Math.round((count / max) * 100);
            return (
              <div key={type} className="dist-row">
                <span className="dist-label">{config.label}</span>
                <div className="dist-bar-wrap">
                  <div
                    className="dist-bar"
                    style={{ width: `${pct}%`, backgroundColor: config.border }}
                  />
                </div>
                <span className="dist-count">{count}</span>
              </div>
            );
          })}
      </div>
    </div>
  );
};

export default EntityDistribution;
