import React, { useEffect, useMemo, useState } from 'react';
import { getLabelingArticles, getReviewQueue, getStats } from '../services/api';
import './AdminDashboardPage.css';

function toEntityTypeKey(entity) {
  return entity?.type || entity?.entity_type || 'UNKNOWN';
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null);
  const [articles, setArticles] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStats(), getLabelingArticles(), getReviewQueue()])
      .then(([sysStats, articleData, reviewData]) => {
        setStats(sysStats);
        setArticles(articleData || []);
        setResults(reviewData || []);
      })
      .finally(() => setLoading(false));
  }, []);

  const aggregates = useMemo(() => {
    const submitted = results.filter((x) => x.status === 'pending_review').length;
    const reviewed = results.filter((x) => x.status !== 'pending_review').length;

    const byType = {};
    let totalEntities = 0;
    results.forEach((item) => {
      (item.corrected_entities || []).forEach((entity) => {
        const key = toEntityTypeKey(entity);
        byType[key] = (byType[key] || 0) + 1;
        totalEntities += 1;
      });
    });

    return {
      submitted,
      reviewed,
      totalEntities,
      byType,
    };
  }, [results]);

  if (loading) {
    return <div className="admin-dashboard-loading">Đang tải dashboard...</div>;
  }

  return (
    <div className="admin-dashboard">
      <h2 className="admin-dashboard-title">Dashboard quản trị</h2>

      <div className="admin-dashboard-grid">
        <div className="admin-dashboard-card">
          <span className="admin-dashboard-value">{stats?.articles ?? 0}</span>
          <span className="admin-dashboard-label">Text đã crawl/xử lý</span>
        </div>
        <div className="admin-dashboard-card">
          <span className="admin-dashboard-value">{aggregates.submitted}</span>
          <span className="admin-dashboard-label">Kết quả gán nhãn chờ xem</span>
        </div>
        <div className="admin-dashboard-card">
          <span className="admin-dashboard-value">{aggregates.reviewed}</span>
          <span className="admin-dashboard-label">Kết quả đã tổng hợp</span>
        </div>
        <div className="admin-dashboard-card">
          <span className="admin-dashboard-value">{aggregates.totalEntities}</span>
          <span className="admin-dashboard-label">Tổng thực thể đã gán</span>
        </div>
      </div>

      <section className="admin-dashboard-section">
        <h3>Tổng hợp dữ liệu gán nhãn theo loại</h3>
        {Object.keys(aggregates.byType).length === 0 && (
          <p className="admin-dashboard-empty">Chưa có dữ liệu gán nhãn.</p>
        )}
        <div className="admin-dashboard-entity-list">
          {Object.entries(aggregates.byType)
            .sort((a, b) => b[1] - a[1])
            .map(([type, count]) => (
              <div key={type} className="admin-dashboard-entity-item">
                <span>{type}</span>
                <strong>{count}</strong>
              </div>
            ))}
        </div>
      </section>

      <section className="admin-dashboard-section">
        <h3>File/text đã crawl và xử lý</h3>
        {articles.length === 0 && (
          <p className="admin-dashboard-empty">Chưa có dữ liệu text.</p>
        )}
        <div className="admin-dashboard-title-list">
          {articles.map((item) => (
            <div key={item.article_id} className="admin-dashboard-title-item">
              <span className="admin-dashboard-title-text">{item.title || item.url || `Bài ${item.article_id}`}</span>
              <span className="admin-dashboard-title-meta">ID {item.article_id}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
