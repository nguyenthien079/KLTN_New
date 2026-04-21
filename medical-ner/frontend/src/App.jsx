import React, { useEffect, useMemo, useState } from 'react';
import { analyzeText, analyzeUrl } from './services/api';
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
  const role = user?.role;

  const roleTabConfig = useMemo(() => {
    if (role === 'chuyen_gia') {
      return [
        { id: 'labeling', label: 'Labeling' },
      ];
    }
    if (role === 'admin') {
      return [
        { id: 'dashboard', label: 'Dashboard' },
        { id: 'data', label: 'Bàn giao' },
        { id: 'review', label: 'Duyệt gán nhãn' },
        { id: 'users', label: 'Quản lý user' },
      ];
    }
    return [
      { id: 'ner', label: 'Phân tích NER' },
      { id: 'labeling', label: 'Labeling' },
    ];
  }, [role]);

  const allowedTabIds = useMemo(() => roleTabConfig.map((t) => t.id), [roleTabConfig]);

  useEffect(() => {
    if (!allowedTabIds.includes(tab)) {
      setTab(allowedTabIds[0] || 'labeling');
    }
  }, [allowedTabIds, tab]);

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

  return (
    <div className="page" onKeyDown={handleKeyDown}>
      <Header />

      <nav className="tab-nav">
        <div className="tab-nav-inner">
          {roleTabConfig.map((t) => (
            <button
              key={t.id}
              className={`tab-btn${tab === t.id ? ' tab-btn--active' : ''}`}
              onClick={() => handleTabChange(t.id)}
            >
              {t.label}
            </button>
          ))}
          <div className="tab-nav-user">
            <span className="tab-nav-username">
              {user.display_name || user.username}
            </span>
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
        {tab === 'labeling' && allowedTabIds.includes('labeling') && <LabelingPage />}
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
