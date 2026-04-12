import React from 'react';

export default function AnnotationView({ articleId, onBack }) {
  return (
    <div style={{ marginTop: 28 }}>
      <button onClick={onBack}>← Quay lại</button>
      <p>AnnotationView (Article {articleId}) — coming soon</p>
    </div>
  );
}
