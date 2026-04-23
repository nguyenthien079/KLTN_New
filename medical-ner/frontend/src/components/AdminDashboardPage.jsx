import React, { useEffect, useMemo, useState, useRef } from 'react';
import { getAdminDashboardSummary, getLabelingArticles, getStats } from '../services/api';
import './AdminDashboardPage.css';

/* ── Pie Chart ─────────────────────────────────────────── */
const CHART_COLORS = [
  '#0284c7', '#0d9488', '#7c3aed', '#db2777',
  '#d97706', '#16a34a', '#dc2626', '#0891b2',
  '#9333ea', '#ea580c',
];

function PieChart({ data }) {
  const [tooltip, setTooltip] = useState(null);
  const [hovered, setHovered] = useState(null);
  const svgRef = useRef(null);

  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) return null;

  const size = 220;
  const cx = size / 2, cy = size / 2;
  const outerR = 88, innerR = 52;

  let cumAngle = -Math.PI / 2;
  const slices = data.map((d, i) => {
    const angle = (d.value / total) * Math.PI * 2;
    const startAngle = cumAngle;
    cumAngle += angle;
    const endAngle = cumAngle;

    const x1 = cx + outerR * Math.cos(startAngle);
    const y1 = cy + outerR * Math.sin(startAngle);
    const x2 = cx + outerR * Math.cos(endAngle);
    const y2 = cy + outerR * Math.sin(endAngle);
    const ix1 = cx + innerR * Math.cos(endAngle);
    const iy1 = cy + innerR * Math.sin(endAngle);
    const ix2 = cx + innerR * Math.cos(startAngle);
    const iy2 = cy + innerR * Math.sin(startAngle);
    const largeArc = angle > Math.PI ? 1 : 0;

    const path = [
      `M ${x1} ${y1}`,
      `A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${ix1} ${iy1}`,
      `A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2} ${iy2}`,
      'Z',
    ].join(' ');

    return { ...d, path, color: CHART_COLORS[i % CHART_COLORS.length], index: i };
  });

  const handleMouseMove = (e, slice) => {
    const rect = svgRef.current.getBoundingClientRect();
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      label: slice.label,
      value: slice.value,
      pct: ((slice.value / total) * 100).toFixed(1),
      color: slice.color,
    });
    setHovered(slice.index);
  };

  const handleMouseLeave = () => {
    setTooltip(null);
    setHovered(null);
  };

  return (
    <div className="adm-pie-wrapper">
      <div className="adm-pie-chart-container">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${size} ${size}`}
          width={size}
          height={size}
          className="adm-pie-svg"
        >
          {slices.map((slice) => (
            <path
              key={slice.label}
              d={slice.path}
              fill={slice.color}
              stroke="#fff"
              strokeWidth="2.5"
              style={{
                transform: hovered === slice.index ? `scale(1.06)` : 'scale(1)',
                transformOrigin: `${cx}px ${cy}px`,
                transition: 'transform 0.2s ease, filter 0.2s ease',
                filter: hovered === slice.index ? 'drop-shadow(0 4px 10px rgba(0,0,0,0.22))' : 'none',
                cursor: 'pointer',
              }}
              onMouseMove={(e) => handleMouseMove(e, slice)}
              onMouseLeave={handleMouseLeave}
            />
          ))}
          <text x={cx} y={cy - 9} textAnchor="middle" className="adm-pie-center-num">
            {total.toLocaleString('vi-VN')}
          </text>
          <text x={cx} y={cy + 12} textAnchor="middle" className="adm-pie-center-label">
            thực thể
          </text>
        </svg>
        {tooltip && (
          <div
            className="adm-pie-tooltip"
            style={{ left: tooltip.x + 14, top: tooltip.y - 14 }}
          >
            <span className="adm-pie-tooltip-dot" style={{ background: tooltip.color }} />
            <strong>{tooltip.label}</strong>
            <span>{tooltip.value.toLocaleString('vi-VN')} ({tooltip.pct}%)</span>
          </div>
        )}
      </div>

      <div className="adm-pie-legend">
        {slices.map((slice) => (
          <div
            key={slice.label}
            className={`adm-pie-legend-item${hovered === slice.index ? ' adm-pie-legend-item--active' : ''}`}
            onMouseEnter={() => setHovered(slice.index)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="adm-pie-legend-dot" style={{ background: slice.color }} />
            <span className="adm-pie-legend-label">{slice.label}</span>
            <div className="adm-pie-legend-right">
              <span className="adm-pie-legend-value">{slice.value.toLocaleString('vi-VN')}</span>
              <span className="adm-pie-legend-pct">{((slice.value / total) * 100).toFixed(1)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Animated Stat Card ─────────────────────────────────── */
function StatCard({ value, label, icon, accent, delay = 0 }) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (!value) return;
    const duration = 900, step = 16;
    const increment = value / (duration / step);
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) { setDisplayed(value); clearInterval(timer); }
      else setDisplayed(Math.floor(current));
    }, step);
    return () => clearInterval(timer);
  }, [value]);

  return (
    <div
      className={`adm-stat-card${accent ? ' adm-stat-card--accent' : ''}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="adm-stat-icon-wrap">
        <span className="adm-stat-icon">{icon}</span>
      </div>
      <div className="adm-stat-body">
        <span className="adm-stat-value">{displayed.toLocaleString('vi-VN')}</span>
        <span className="adm-stat-label">{label}</span>
      </div>
    </div>
  );
}

/* ── Main ───────────────────────────────────────────────── */
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
      .catch(() => { setStats(null); setArticles([]); setSummary(null); })
      .finally(() => setLoading(false));
  }, []);

  const aggregates = useMemo(() => ({
    submitted: summary?.submitted ?? 0,
    reviewed: summary?.reviewed ?? 0,
    totalEntities: summary?.total_annotations ?? 0,
    byType: summary?.annotations_by_type || {},
  }), [summary]);

  const pieData = useMemo(() =>
    Object.entries(aggregates.byType)
      .sort((a, b) => b[1] - a[1])
      .map(([label, value]) => ({ label, value })),
    [aggregates.byType]
  );

  if (loading) {
    return (
      <div className="adm-loading">
        <div className="adm-loading-ring"><div/><div/><div/><div/></div>
        <p>Đang tải dữ liệu…</p>
      </div>
    );
  }

  const cards = [
    { value: stats?.articles ?? 0,    label: 'Văn bản đã crawl',       icon: '📄', accent: false },
    { value: aggregates.submitted,     label: 'Chờ xem xét',            icon: '⏳', accent: true  },
    { value: aggregates.reviewed,      label: 'Đã tổng hợp',            icon: '✅', accent: false },
    { value: aggregates.totalEntities, label: 'Tổng thực thể đã gán',   icon: '🏷️', accent: false },
  ];

  return (
    <div className="adm-root">
      <header className="adm-header">
        <div>
          <h2 className="adm-title">Dashboard Quản Trị</h2>
          <p className="adm-subtitle">Tổng quan hệ thống gán nhãn dữ liệu NLP</p>
        </div>
        <div className="adm-live-pill">
          <span className="adm-live-dot" />
          Live
        </div>
      </header>

      <div className="adm-cards-grid">
        {cards.map((c, i) => (
          <StatCard key={c.label} {...c} delay={i * 90} />
        ))}
      </div>

      <section className="adm-section">
        <div className="adm-section-hd">
          <span className="adm-section-bar" />
          <h3 className="adm-section-title">Tổng hợp dữ liệu gán nhãn theo loại</h3>
        </div>
        {pieData.length === 0 ? (
          <div className="adm-empty"><span>📊</span><p>Chưa có dữ liệu gán nhãn.</p></div>
        ) : (
          <PieChart data={pieData} />
        )}
      </section>

      <section className="adm-section">
        <div className="adm-section-hd">
          <span className="adm-section-bar" />
          <h3 className="adm-section-title">File / Text đã crawl và xử lý</h3>
          <span className="adm-count-badge">{articles.length}</span>
        </div>
        {articles.length === 0 ? (
          <div className="adm-empty"><span>📂</span><p>Chưa có dữ liệu text.</p></div>
        ) : (
          <div className="adm-article-list">
            {articles.map((item, idx) => (
              <div key={item.article_id} className="adm-article-item">
                <span className="adm-article-idx">{idx + 1}</span>
                <span className="adm-article-text">
                  {item.title || item.url || `Bài ${item.article_id}`}
                </span>
                <span className="adm-article-id">#{item.article_id}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}