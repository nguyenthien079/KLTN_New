import React, { useState } from 'react';
import { loginUser } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import './LoginPage.css';

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Vui lòng nhập đầy đủ thông tin.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await loginUser(username.trim(), password);
      login(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Đăng nhập thất bại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-bg-pattern" aria-hidden="true" />

      <div className="login-card">
        <div className="login-brand">
          <div className="login-brand-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <rect width="28" height="28" rx="8" fill="var(--color-primary)" />
              <path d="M14 6v16M6 14h16" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <h1 className="login-title">Medical NER</h1>
            <p className="login-subtitle">Hệ thống nhận diện thực thể y tế</p>
          </div>
        </div>

        <div className="login-divider" />

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <div className="login-field">
            <label className="login-label" htmlFor="lp-username">Tên đăng nhập</label>
            <input
              id="lp-username"
              className="login-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              placeholder="Nhập tên đăng nhập"
            />
          </div>

          <div className="login-field">
            <label className="login-label" htmlFor="lp-password">Mật khẩu</label>
            <input
              id="lp-password"
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="login-error" role="alert">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <circle cx="7" cy="7" r="6.5" stroke="currentColor" />
                <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? (
              <>
                <span className="login-spinner" aria-hidden="true" />
                Đang đăng nhập…
              </>
            ) : (
              'Đăng nhập'
            )}
          </button>
        </form>
      </div>

      <p className="login-footer">
        Hệ thống NER · PhoBERT + Ensemble Model
      </p>
    </div>
  );
}