import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMessage: '' };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      errorMessage: error?.message || 'Đã xảy ra lỗi không xác định.',
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled UI error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f8fafc',
          padding: '20px',
        }}>
          <div style={{
            maxWidth: '560px',
            width: '100%',
            background: '#ffffff',
            border: '1px solid #cbd5e1',
            borderRadius: '12px',
            padding: '20px',
            boxShadow: '0 6px 20px rgba(15, 23, 42, 0.08)',
          }}>
            <h2 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', color: '#0f172a' }}>
              Ứng dụng gặp lỗi khi tải giao diện
            </h2>
            <p style={{ margin: '0 0 14px 0', color: '#475569', lineHeight: 1.55 }}>
              Thay vì màn hình trắng, hệ thống đã chặn lỗi để bạn có thể tải lại an toàn.
            </p>
            <p style={{
              margin: '0 0 14px 0',
              padding: '10px',
              borderRadius: '8px',
              background: '#f1f5f9',
              color: '#334155',
              fontSize: '0.88rem',
              wordBreak: 'break-word',
            }}>
              {this.state.errorMessage}
            </p>
            <button
              onClick={this.handleReload}
              style={{
                border: 'none',
                background: '#0284c7',
                color: '#fff',
                borderRadius: '8px',
                padding: '9px 14px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Tải lại trang
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;