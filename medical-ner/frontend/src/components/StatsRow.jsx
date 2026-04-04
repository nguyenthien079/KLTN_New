import React from 'react';

const StatCard = ({ value, label }) => (
  <div className="stat-card">
    <span className="stat-value">{value}</span>
    <span className="stat-label">{label}</span>
  </div>
);

const StatsRow = ({ totalSentences, totalEntities, processingTimeMs }) => (
  <div className="stats-row">
    <StatCard value={totalSentences} label="Số câu" />
    <StatCard value={totalEntities} label="Thực thể" />
    <StatCard value={`${processingTimeMs} ms`} label="Thời gian xử lý" />
  </div>
);

export default StatsRow;
