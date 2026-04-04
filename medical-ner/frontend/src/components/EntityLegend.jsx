import React from 'react';
import { ENTITY_CONFIG } from '../config/entityConfig';

const EntityLegend = () => (
  <aside className="entity-legend">
    <h2 className="legend-title">Loại thực thể</h2>
    <div className="legend-grid">
      {Object.entries(ENTITY_CONFIG).map(([type, config]) => (
        <div key={type} className="legend-item">
          <span
            className="legend-dot"
            style={{ backgroundColor: config.border }}
          />
          <div className="legend-info">
            <span className="legend-label">{config.label}</span>
            <span className="legend-desc">{config.description}</span>
          </div>
        </div>
      ))}
    </div>
  </aside>
);

export default EntityLegend;
