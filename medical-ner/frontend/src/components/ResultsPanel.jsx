import React from 'react';
import StatsRow from './StatsRow';
import EntityDistribution from './EntityDistribution';
import HighlightedSentence from './HighlightedSentence';

const ResultsPanel = ({ results }) => {
  const { sentences, stats, processing_time_ms } = results;

  return (
    <section className="results-panel">
      <h2 className="results-title">Kết quả phân tích</h2>

      <StatsRow
        totalSentences={stats.total_sentences}
        totalEntities={stats.total_entities}
        processingTimeMs={processing_time_ms}
      />

      {stats.by_type && Object.keys(stats.by_type).length > 0 && (
        <EntityDistribution byType={stats.by_type} />
      )}

      <div className="sentences-list">
        {sentences.map((sent, idx) => (
          <div key={idx} className="sentence-block">
            <span className="sentence-num">Câu {idx + 1}</span>
            <HighlightedSentence
              sentence={sent.sentence}
              entities={sent.entities}
            />
          </div>
        ))}
      </div>
    </section>
  );
};

export default ResultsPanel;
