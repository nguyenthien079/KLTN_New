import React from 'react';

const SAMPLE_TEXT =
  'Bệnh nhân nam 45 tuổi nhập viện với triệu chứng sốt cao 39 độ C, ho có đờm, đau ngực. ' +
  'Chẩn đoán: viêm phổi nặng. Điều trị: kháng sinh cephalosporin, paracetamol hạ sốt. ' +
  'Kết quả X-quang ngực cho thấy tổn thương thùy dưới phổi phải.';

const InputPanel = ({ inputType, inputValue, loading, error, onTypeChange, onValueChange, onAnalyze, onSample }) => (
  <section className="input-panel">
    <div className="tab-bar">
      <button
        className={`tab-btn${inputType === 'text' ? ' active' : ''}`}
        onClick={() => onTypeChange('text')}
        type="button"
      >
        Văn bản
      </button>
      <button
        className={`tab-btn${inputType === 'url' ? ' active' : ''}`}
        onClick={() => onTypeChange('url')}
        type="button"
      >
        URL bài báo
      </button>
    </div>

    <p className="input-note">
      {inputType === 'text'
        ? 'Lưu ý: chỉ dán văn bản thuần, không dán URL vào đây.'
        : 'Lưu ý: chỉ nhập URL bài báo, không dán văn bản vào đây.'}
    </p>

    {inputType === 'text' ? (
      <textarea
        className="input-field input-textarea"
        placeholder="Nhập văn bản y tế tiếng Việt..."
        value={inputValue}
        onChange={(e) => onValueChange(e.target.value)}
        rows={7}
        spellCheck={false}
      />
    ) : (
      <input
        className="input-field input-url"
        type="url"
        placeholder="https://suckhoedoisong.vn/..."
        value={inputValue}
        onChange={(e) => onValueChange(e.target.value)}
      />
    )}

    <div className="action-row">
      <button
        className="btn btn-primary"
        onClick={onAnalyze}
        disabled={loading}
        type="button"
      >
        {loading ? (
          <>
            <span className="spinner" aria-hidden="true" />
            Đang phân tích...
          </>
        ) : (
          'Phân tích'
        )}
      </button>
      {inputType === 'text' && (
        <button
          className="btn btn-secondary"
          onClick={() => onSample(SAMPLE_TEXT)}
          disabled={loading}
          type="button"
        >
          Văn bản mẫu
        </button>
      )}
    </div>

    {error && (
      <div className="error-box" role="alert">
        {error}
      </div>
    )}
  </section>
);

export default InputPanel;
