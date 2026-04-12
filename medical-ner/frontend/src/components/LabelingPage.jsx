// frontend/src/components/LabelingPage.jsx
import React, { useState, useEffect } from 'react';
import { getLabelingArticles } from '../services/api';
import AnnotationView from './AnnotationView';
import './LabelingPage.css';

export default function LabelingPage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null); // article_id being annotated

  useEffect(() => {
    getLabelingArticles()
      .then(setArticles)
      .catch(() => setArticles([]))
      .finally(() => setLoading(false));
  }, []);

  if (selected) {
    return (
      <AnnotationView
        articleId={selected}
        onBack={() => setSelected(null)}
      />
    );
  }

  const STATUS_LABEL = {
    submitted: 'Đã nộp',
    draft: 'Đang làm',
  };

  return (
    <div className="labeling-page">
      <div className="labeling-header">
        <h2 className="labeling-title">Danh sách bài cần gán nhãn</h2>
        <span className="labeling-count">{articles.length} bài</span>
      </div>

      {loading && <p className="labeling-loading">Đang tải...</p>}

      <div className="labeling-table-wrap">
        <table className="labeling-table">
          <thead>
            <tr>
              <th>Tiêu đề / URL</th>
              <th>Labelers</th>
              <th>Trạng thái của bạn</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.article_id}>
                <td className="labeling-title-cell">
                  {a.assigned_to_me && (
                    <span className="labeling-assigned-badge">Được assign</span>
                  )}
                  <span className="labeling-article-title">
                    {a.title || a.url}
                  </span>
                </td>
                <td className="labeling-count-cell">{a.submission_count}</td>
                <td>
                  {a.my_status ? (
                    <span className={`labeling-status labeling-status--${a.my_status}`}>
                      {STATUS_LABEL[a.my_status]}
                    </span>
                  ) : (
                    <span className="labeling-status labeling-status--none">Chưa làm</span>
                  )}
                </td>
                <td>
                  <button
                    className="labeling-btn"
                    onClick={() => setSelected(a.article_id)}
                  >
                    Label
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
