import React, { useState } from 'react';
import { analyzeText, analyzeUrl } from './services/api';
import HighlightedSentence from './components/HighlightedSentence';
import './App.css';

const SAMPLE_TEXT = 'Bệnh nhân nam 45 tuổi nhập viện với triệu chứng sốt cao 39 độ C, ho có đờm, đau ngực. Chẩn đoán: viêm phổi nặng. Điều trị: kháng sinh cephalosporin, paracetamol hạ sốt.';

function App() {
  const [inputType, setInputType] = useState('text');
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!inputValue.trim()) {
      setError('Vui lòng nhập nội dung');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = inputType === 'text'
        ? await analyzeText(inputValue)
        : await analyzeUrl(inputValue);
      setResults(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Lỗi khi phân tích');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Vietnamese Medical NER System</h1>
        <p>Hệ thống nhận diện thực thể y tế tiếng Việt</p>
      </header>

      <div className="container">
        <div className="input-section">
          <div className="input-type-selector">
            <button
              className={inputType === 'text' ? 'active' : ''}
              onClick={() => setInputType('text')}
            >
              Van ban
            </button>
            <button
              className={inputType === 'url' ? 'active' : ''}
              onClick={() => setInputType('url')}
            >
              URL
            </button>
          </div>

          {inputType === 'text' ? (
            <textarea
              className="input-textarea"
              placeholder="Nhap van ban y te tieng Viet..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              rows={6}
            />
          ) : (
            <input
              className="input-url"
              type="text"
              placeholder="https://suckhoedoisong.vn/..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
            />
          )}

          <div className="button-group">
            <button
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={loading}
            >
              {loading ? 'Dang phan tich...' : 'Phan tich'}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => { setInputType('text'); setInputValue(SAMPLE_TEXT); }}
            >
              Van ban mau
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}
        </div>

        {results && (
          <div className="results-section">
            <div className="stats-panel">
              <h3>Thong ke</h3>
              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-label">So cau:</span>
                  <span className="stat-value">{results.stats.total_sentences}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Entities:</span>
                  <span className="stat-value">{results.stats.total_entities}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Thoi gian:</span>
                  <span className="stat-value">{results.processing_time_ms} ms</span>
                </div>
              </div>

              <div className="entity-breakdown">
                <h4>Phan loai Entities:</h4>
                {Object.entries(results.stats.by_type || {}).map(([type, count]) => (
                  <div key={type} className="entity-count">
                    <span>{type}:</span>
                    <span className="count-badge">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="sentences-panel">
              <h3>Ket qua phan tich</h3>
              {results.sentences.map((sent, idx) => (
                <div key={idx} className="sentence-block">
                  <div className="sentence-number">Cau {idx + 1}:</div>
                  <HighlightedSentence
                    sentence={sent.sentence}
                    entities={sent.entities}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
