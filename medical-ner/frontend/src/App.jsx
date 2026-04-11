import React, { useState } from 'react';
import { analyzeText, analyzeUrl } from './services/api';
import Header from './components/Header';
import InputPanel from './components/InputPanel';
import EntityLegend from './components/EntityLegend';
import ResultsPanel from './components/ResultsPanel';
import SystemStats from './components/SystemStats';
import CrawlPage from './components/CrawlPage';
import './App.css';

function App() {
  const [inputType, setInputType] = useState('text');
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('ner');

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
          <button
            className={`tab-btn${tab === 'ner' ? ' tab-btn--active' : ''}`}
            onClick={() => handleTabChange('ner')}
          >
            Phân tích NER
          </button>
          <button
            className={`tab-btn${tab === 'crawl' ? ' tab-btn--active' : ''}`}
            onClick={() => handleTabChange('crawl')}
          >
            Thu thập dữ liệu
          </button>
        </div>
      </nav>

      <div className="content-wrap">
        {tab === 'ner' && (
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
        {tab === 'crawl' && <CrawlPage />}
      </div>

      <footer className="site-footer">
        <p>Hệ thống Nhận diện Thực thể Y tế Tiếng Việt · PhoBERT + Ensemble Model</p>
      </footer>
    </div>
  );
}

export default App;
