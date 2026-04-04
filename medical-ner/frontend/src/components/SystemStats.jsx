import React, { useEffect, useState } from 'react';
import { getStats } from '../services/api';

const SystemStats = () => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  if (!stats) return null;

  return (
    <section className="system-stats">
      <h2 className="system-stats-title">Dữ liệu hệ thống</h2>
      <div className="system-stats-grid">
        <div className="sys-stat-card">
          <span className="sys-stat-value">{stats.articles?.toLocaleString() ?? '—'}</span>
          <span className="sys-stat-label">Bài viết đã thu thập</span>
        </div>
        <div className="sys-stat-card">
          <span className="sys-stat-value">{stats.sentences?.toLocaleString() ?? '—'}</span>
          <span className="sys-stat-label">Câu đã xử lý</span>
        </div>
        <div className="sys-stat-card">
          <span className="sys-stat-value">{stats.entities?.total?.toLocaleString() ?? '—'}</span>
          <span className="sys-stat-label">Thực thể trong cơ sở dữ liệu</span>
        </div>
      </div>
    </section>
  );
};

export default SystemStats;
