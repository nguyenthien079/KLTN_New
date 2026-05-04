import React, { useEffect, useMemo, useRef, useState } from 'react';
import { analyzeText, analyzeUrl, getLabelingNotifications } from './services/api';
import { useAuth } from './contexts/AuthContext';
import Header from './components/Header';
import InputPanel from './components/InputPanel';
import EntityLegend from './components/EntityLegend';
import ResultsPanel from './components/ResultsPanel';
import SystemStats from './components/SystemStats';
import CrawlPage from './components/CrawlPage';
import PipelinePage from './components/PipelinePage';
import ReviewPage from './components/ReviewPage';
import UsersPage from './components/UsersPage';
import LoginPage from './components/LoginPage';
import LabelingPage from './components/LabelingPage';
import AdminDashboardPage from './components/AdminDashboardPage';
import DataListPage from './components/DataListPage';
import './App.css';

function App() {
  const { user, logout } = useAuth();

  const [inputType, setInputType] = useState('text');
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('labeling');
  const [notifications, setNotifications] = useState([]);
  const [readNotificationKeys, setReadNotificationKeys] = useState([]);
  const [isBellOpen, setIsBellOpen] = useState(false);
  const [labelingFocusRequest, setLabelingFocusRequest] = useState(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const bellRef = useRef(null);
  const roles = useMemo(
    () => (Array.isArray(user?.roles)
      ? user.roles
      : String(user?.role || '')
          .split(',')
          .map((r) => r.trim())
          .filter(Boolean)),
    [user?.roles, user?.role]
  );
  const hasRole = (roleName) => roles.includes(roleName);
  const notificationReadStorageKey = useMemo(
    () => `labeling_read_notifications_${user?.user_id || 'anonymous'}`,
    [user?.user_id]
  );

  const roleTabConfig = useMemo(() => {
    const tabs = [];
    if (hasRole('admin')) {
      tabs.push(
        { id: 'dashboard', label: 'Dashboard' },
        { id: 'data', label: 'Bàn giao' },
        { id: 'users', label: 'Quản lý user' }
      );
    }
    if (hasRole('reviewer')) {
      tabs.push({ id: 'review', label: 'Duyệt gán nhãn' });
    }
    if (hasRole('chuyen_gia')) {
      tabs.push({ id: 'labeling', label: 'Labeling' });
    }
    if (tabs.length === 0) {
      tabs.push({ id: 'labeling', label: 'Labeling' });
    }
    return tabs;
  }, [roles]);

  const allowedTabIds = useMemo(() => roleTabConfig.map((t) => t.id), [roleTabConfig]);

  useEffect(() => {
    if (!allowedTabIds.includes(tab)) {
      setTab(allowedTabIds[0] || 'labeling');
    }
  }, [allowedTabIds, tab]);

  useEffect(() => {
    if (!hasRole('chuyen_gia')) {
      setNotifications([]);
      setReadNotificationKeys([]);
      setIsBellOpen(false);
      return;
    }

    getLabelingNotifications(12)
      .then((data) => setNotifications(data || []))
      .catch(() => setNotifications([]));
  }, [roles, user?.user_id]);

  useEffect(() => {
    if (!hasRole('chuyen_gia')) return;
    try {
      const raw = localStorage.getItem(notificationReadStorageKey);
      const parsed = raw ? JSON.parse(raw) : [];
      setReadNotificationKeys(Array.isArray(parsed) ? parsed : []);
    } catch {
      setReadNotificationKeys([]);
    }
  }, [notificationReadStorageKey, roles]);

  useEffect(() => {
    if (!hasRole('chuyen_gia')) return;
    try {
      localStorage.setItem(notificationReadStorageKey, JSON.stringify(readNotificationKeys));
    } catch {
      // Ignore localStorage write errors.
    }
  }, [readNotificationKeys, notificationReadStorageKey, roles]);

  const notificationItems = useMemo(
    () => notifications.map((item) => {
      const message = String(item?.message || '');
      const key = `${item?.article_id || ''}|${item?.created_at || ''}|${message}`;
      const isRejected = message.toLowerCase().includes('từ chối') || message.toLowerCase().includes('tu choi');
      const isRead = readNotificationKeys.includes(key);
      return {
        ...item,
        key,
        isRejected,
        isRead,
      };
    }),
    [notifications, readNotificationKeys]
  );

  const unreadNotificationCount = useMemo(
    () => notificationItems.filter((item) => !item.isRead).length,
    [notificationItems]
  );

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (bellRef.current && !bellRef.current.contains(event.target)) {
        setIsBellOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!user) return <LoginPage />;

  const handleTypeChange = (type) => {
    setInputType(type);
    setInputValue('');
    setResults(null);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (!inputValue.trim()) {
      setError('Vui lòng nhập nội dung cần phân tích.');
      return;
    }
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const data =
        inputType === 'text'
          ? await analyzeText(inputValue)
          : await analyzeUrl(inputValue);
      setResults(data);
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Lỗi kết nối. Vui lòng kiểm tra backend.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (tab === 'ner' && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleAnalyze();
    }
  };

  const handleTabChange = (newTab) => {
    if (!allowedTabIds.includes(newTab)) return;
    setTab(newTab);
    if (newTab !== 'ner') {
      setLoading(false);
      setError(null);
    }
  };

  const markNotificationAsRead = (key) => {
    setReadNotificationKeys((prev) => (prev.includes(key) ? prev : [...prev, key]));
  };

  const markAllNotificationsAsRead = () => {
    setReadNotificationKeys((prev) => {
      const merged = new Set(prev);
      notificationItems.forEach((item) => merged.add(item.key));
      return Array.from(merged);
    });
  };

  const openNotificationArticle = (notificationItem) => {
    markNotificationAsRead(notificationItem.key);
    setTab('labeling');
    setLabelingFocusRequest({ articleId: notificationItem.article_id, nonce: Date.now() });
    setIsBellOpen(false);
  };

  return (
    <div className="page" onKeyDown={handleKeyDown}>
      <Header />

      <nav className="tab-nav">
        <div className="tab-nav-inner">
          {roleTabConfig.length > 1 && (
            <button
              className={`tab-nav-hamburger${isMenuOpen ? ' tab-nav-hamburger--active' : ''}`}
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              title="Menu"
              aria-label="Mở menu"
            >
              <span></span>
              <span></span>
              <span></span>
            </button>
          )}
          <div className={`tab-nav-menu${isMenuOpen ? ' tab-nav-menu--open' : ''}`}>
            {roleTabConfig.map((t) => (
              <button
                key={t.id}
                className={`tab-btn${tab === t.id ? ' tab-btn--active' : ''}`}
                onClick={() => {
                  handleTabChange(t.id);
                  setIsMenuOpen(false);
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="tab-nav-user">
            <span className="tab-nav-username">
              {user.display_name || user.username}
            </span>
            {hasRole('chuyen_gia') && (
              <div className="tab-nav-bell-wrap" ref={bellRef}>
                <button
                  className={`tab-nav-bell-btn${isBellOpen ? ' tab-nav-bell-btn--active' : ''}`}
                  onClick={() => setIsBellOpen((prev) => !prev)}
                  title="Thông báo"
                >
                  <span className="tab-nav-bell-icon" aria-hidden="true">🔔</span>
                  {unreadNotificationCount > 0 && (
                    <span className="tab-nav-bell-badge">{unreadNotificationCount}</span>
                  )}
                </button>

                {isBellOpen && (
                  <div className="tab-nav-bell-panel">
                    <div className="tab-nav-bell-header">
                      <strong>Thông báo</strong>
                      {notificationItems.length > 0 && unreadNotificationCount > 0 && (
                        <button
                          type="button"
                          className="tab-nav-bell-mark-all"
                          onClick={markAllNotificationsAsRead}
                        >
                          Đánh dấu tất cả đã đọc
                        </button>
                      )}
                    </div>
                    <div className="tab-nav-bell-list">
                      {notificationItems.length === 0 && (
                        <p className="tab-nav-bell-empty">Hiện chưa có thông báo mới.</p>
                      )}
                      {notificationItems.map((item) => (
                        <button
                          key={item.key}
                          className={`tab-nav-bell-item${item.isRejected ? ' tab-nav-bell-item--reject' : ''}${item.isRead ? ' tab-nav-bell-item--read' : ''}`}
                          onClick={() => openNotificationArticle(item)}
                        >
                          <span>{item.message}</span>
                          <em>Mở file</em>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            <button className="tab-nav-logout" onClick={logout}>
              Đăng xuất
            </button>
          </div>
        </div>
      </nav>

      <div className={`content-wrap${tab === 'labeling' || tab === 'data' ? ' content-wrap--wide' : ''}`}>
        {tab === 'dashboard' && allowedTabIds.includes('dashboard') && <AdminDashboardPage />}
        {tab === 'data' && allowedTabIds.includes('data') && <DataListPage />}
        {tab === 'ner' && allowedTabIds.includes('ner') && (
          <>
            <div className="main-grid">
              <InputPanel
                inputType={inputType}
                inputValue={inputValue}
                loading={loading}
                error={error}
                onTypeChange={handleTypeChange}
                onValueChange={setInputValue}
                onAnalyze={handleAnalyze}
                onSample={(text) => { setInputValue(text); setResults(null); setError(null); }}
              />
              <EntityLegend />
            </div>
            {results && <ResultsPanel results={results} />}
            <SystemStats />
          </>
        )}
        {tab === 'crawl' && allowedTabIds.includes('crawl') && <CrawlPage />}
        {tab === 'pipeline' && allowedTabIds.includes('pipeline') && <PipelinePage />}
        {tab === 'labeling' && allowedTabIds.includes('labeling') && <LabelingPage focusRequest={labelingFocusRequest} />}
        {tab === 'review' && allowedTabIds.includes('review') && <ReviewPage />}
        {tab === 'users' && allowedTabIds.includes('users') && <UsersPage />}
      </div>

      <footer className="site-footer">
        <p>Hệ thống Nhận diện Thực thể Y tế Tiếng Việt · PhoBERT + Ensemble Model</p>
      </footer>
    </div>
  );
}

export default App;
