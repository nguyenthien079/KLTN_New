import React, { useEffect, useMemo, useState } from 'react';
import { getLabelingArticle, getLabelingArticles } from '../services/api';
import './DataListPage.css';

export default function DataListPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    getLabelingArticles()
      .then((data) => {
        setItems(data || []);
        if (data?.length) setSelectedId(data[0].article_id);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    getLabelingArticle(selectedId).then(setDetail).catch(() => setDetail(null));
  }, [selectedId]);

  const selectedTitle = useMemo(() => {
    const current = items.find((x) => x.article_id === selectedId);
    return current?.title || current?.url || '—';
  }, [items, selectedId]);

  return (
    <div className="data-list-page">
      <h2 className="data-list-title">Danh sách file/text</h2>
      <div className="data-list-layout">
        <div className="data-list-table-wrap">
          {loading ? (
            <p className="data-list-loading">Đang tải dữ liệu...</p>
          ) : (
            <table className="data-list-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Tiêu đề / URL</th>
                  <th>Lượt gán nhãn</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.article_id}
                    className={selectedId === item.article_id ? 'data-list-row--active' : ''}
                    onClick={() => setSelectedId(item.article_id)}
                  >
                    <td>{item.article_id}</td>
                    <td>{item.title || item.url}</td>
                    <td>{item.submission_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="data-list-preview-wrap">
          <h3 className="data-list-preview-title">{selectedTitle}</h3>
          <div className="data-list-preview-content">
            {detail?.clean_text || 'Chọn một bản ghi để xem nội dung text đã xử lý.'}
          </div>
        </div>
      </div>
    </div>
  );
}
