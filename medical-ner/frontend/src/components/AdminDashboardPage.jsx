import React, { useEffect, useMemo, useState } from 'react';
import { getAdminDashboardSummary, getLabelingArticles, getStats } from '../services/api';
import './AdminDashboardPage.css';

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null);
  const [articles, setArticles] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStats(), getLabelingArticles(), getAdminDashboardSummary()])
      .then(([sysStats, articleData, summaryData]) => {
        setStats(sysStats || null);
        setArticles(articleData || []);
        setSummary(summaryData || null);
      })
      .catch(() => {
        setStats(null);
        setArticles([]);
        setSummary(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const aggregates = useMemo(() => {
    return {
      submitted: summary?.submitted ?? 0,
      reviewed: summary?.reviewed ?? 0,
      totalEntities: summary?.total_annotations ?? 0,
      byType: summary?.annotations_by_type || {},
    };
  }, [summary]);

  if (loading) {
    return (
      <div className="admin-dashboard-loading">
        <span className="admin-dashboard-spinner" />
        Đang tải dashboard…
      </div>
    );
  }

  const summaryCards = [
    { value: stats?.articles ?? 0,    label: 'Text đã crawl/xử lý',      accent: false, icon: '📄' },
    { value: aggregates.submitted,    label: 'Kết quả gán nhãn chờ xem', accent: true,  icon: '⏳' },
    { value: aggregates.reviewed,     label: 'Kết quả đã tổng hợp',      accent: false, icon: '✅' },
    { value: aggregates.totalEntities,label: 'Tổng thực thể đã gán',     accent: false, icon: '🏷️' },
  ];

  return (
    <div className="admin-dashboard">
      <h2 className="admin-dashboard-title">Dashboard quản trị</h2>

      {/* Summary cards */}
      <div className="admin-dashboard-grid">
        {summaryCards.map(({ value, label, accent, icon }) => (
          <div key={label} className={`admin-dashboard-card${accent ? ' admin-dashboard-card--accent' : ''}`}>
            <div className="admin-dashboard-card-icon" aria-hidden="true">{icon}</div>
            <span className="admin-dashboard-value">{value}</span>
            <span className="admin-dashboard-label">{label}</span>
          </div>
        ))}
      </div>

      {/* Entity breakdown */}
      <section className="admin-dashboard-section">
        <h3 className="admin-dashboard-section-title">Tổng hợp dữ liệu gán nhãn theo loại</h3>
        {Object.keys(aggregates.byType).length === 0 ? (
          <p className="admin-dashboard-empty">Chưa có dữ liệu gán nhãn.</p>
        ) : (
          <div className="admin-dashboard-entity-list">
            {Object.entries(aggregates.byType)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => (
                <div key={type} className="admin-dashboard-entity-item">
                  <span className="admin-dashboard-entity-type">{type}</span>
                  <strong className="admin-dashboard-entity-count">{count}</strong>
                </div>
              ))}
          </div>
        )}
      </section>

      {/* Article list */}
      <section className="admin-dashboard-section">
        <h3 className="admin-dashboard-section-title">File/text đã crawl và xử lý</h3>
        {articles.length === 0 ? (
          <p className="admin-dashboard-empty">Chưa có dữ liệu text.</p>
        ) : (
          <div className="admin-dashboard-title-list">
            {articles.map((item) => (
              <div key={item.article_id} className="admin-dashboard-title-item">
                <span className="admin-dashboard-title-text">
                  {item.title || item.url || `Bài ${item.article_id}`}
                </span>
                <span className="admin-dashboard-title-meta">ID {item.article_id}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}