import React from 'react';

const Header = () => (
  <header className="site-header">
    <div className="header-inner">
      <div className="header-brand">
        <div className="header-brand-icon" aria-hidden="true">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="9" fill="rgba(255,255,255,0.15)" />
            <path d="M16 7v18M7 16h18" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <h1 className="header-title">Nhận diện Thực thể Y tế Tiếng Việt</h1>
          <p className="header-subtitle">
            Phân tích văn bản y tế · PhoBERT + Dictionary + Rule-based Ensemble
          </p>
        </div>
      </div>
    </div>
  </header>
);

export default Header;