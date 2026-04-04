import { useState } from 'react';
import StatsRow from './StatsRow';
import EntityDistribution from './EntityDistribution';
import HighlightedSentence from './HighlightedSentence';
import AnnotationSentence from './AnnotationSentence';
import { submitFeedback } from '../services/api';

const ResultsPanel = ({ results }) => {
  const { sentences, stats, processing_time_ms } = results;

  const [isAnnotating, setIsAnnotating] = useState(false);
  const [editedSentences, setEditedSentences] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null); // null | 'saving' | 'saved' | 'error'

  // Start annotation mode
  const startAnnotating = () => {
    // Deep copy to avoid mutating original results
    setEditedSentences(JSON.parse(JSON.stringify(sentences)));
    setIsAnnotating(true);
    setSaveStatus(null);
  };

  // Cancel annotation mode
  const cancelAnnotating = () => {
    setIsAnnotating(false);
    setEditedSentences(null);
    setSaveStatus(null);
  };

  // Update entities for a specific sentence
  const handleEntitiesChange = (sentenceIdx, newEntities) => {
    setEditedSentences(prev => {
      const next = [...prev];
      next[sentenceIdx] = { ...next[sentenceIdx], entities: newEntities };
      return next;
    });
  };

  // Save corrections to backend
  const handleSave = async () => {
    setSaveStatus('saving');
    
    try {
      const corrections = editedSentences.map((s, i) => ({
        original_text: s.sentence,
        original_entities: sentences[i].entities,
        corrected_entities: s.entities
      }));

      const response = await submitFeedback({ corrections });
      setSaveStatus('saved');
      
      // Auto-hide success message and exit annotation mode after 3s
      setTimeout(() => {
        setIsAnnotating(false);
        setSaveStatus(null);
      }, 3000);
    } catch (error) {
      console.error('Error saving corrections:', error);
      setSaveStatus('error');
    }
  };

  return (
    <section className="results-panel">
      <div className="results-header">
        <h2 className="results-title">Kết quả phân tích</h2>
        
        {!isAnnotating && (
          <button
            className="btn-annotate"
            onClick={startAnnotating}
            title="Chỉnh sửa và gán nhãn lại các thực thể"
          >
            📝 Gán nhãn lại
          </button>
        )}

        {isAnnotating && (
          <div className="annotation-actions">
            <button
              className="btn-save"
              onClick={handleSave}
              disabled={saveStatus === 'saving'}
            >
              {saveStatus === 'saving' ? '⏳ Đang lưu...' : '💾 Lưu nhãn'}
            </button>
            <button
              className="btn-cancel"
              onClick={cancelAnnotating}
              disabled={saveStatus === 'saving'}
            >
              ❌ Hủy
            </button>
          </div>
        )}
      </div>

      {/* Annotation mode banner */}
      {isAnnotating && saveStatus !== 'saved' && (
        <div className="annotation-banner">
          ℹ️ <strong>Đang ở chế độ gán nhãn</strong> — Click vào entity để sửa/xóa, bôi đen text để thêm entity mới
        </div>
      )}

      {/* Success banner */}
      {saveStatus === 'saved' && (
        <div className="success-banner">
          ✅ <strong>Đã lưu {editedSentences.length} câu vào hệ thống</strong> — Dữ liệu có thể dùng để huấn luyện model
        </div>
      )}

      {/* Error banner */}
      {saveStatus === 'error' && (
        <div className="error-banner">
          ❌ <strong>Lỗi khi lưu dữ liệu</strong> — Vui lòng thử lại
        </div>
      )}

      <StatsRow
        totalSentences={stats.total_sentences}
        totalEntities={stats.total_entities}
        processingTimeMs={processing_time_ms}
      />

      {stats.by_type && Object.keys(stats.by_type).length > 0 && (
        <EntityDistribution byType={stats.by_type} />
      )}

      <div className="sentences-list">
        {(isAnnotating ? editedSentences : sentences).map((sent, idx) => (
          <div key={idx} className="sentence-block">
            <span className="sentence-num">Câu {idx + 1}</span>
            
            {isAnnotating ? (
              <AnnotationSentence
                sentence={sent.sentence}
                entities={sent.entities}
                onEntitiesChange={(newEntities) => handleEntitiesChange(idx, newEntities)}
              />
            ) : (
              <HighlightedSentence
                sentence={sent.sentence}
                entities={sent.entities}
              />
            )}
          </div>
        ))}
      </div>
    </section>
  );
};

export default ResultsPanel;
