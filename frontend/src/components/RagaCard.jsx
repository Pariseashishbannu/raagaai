import { ChevronRight } from 'lucide-react';

const RASA_COLORS = {
  karuna: '#3b82f6',
  shringara: '#f43f5e',
  bhakti: '#fbbf24',
  veera: '#ef4444',
  shanta: '#10b981',
  mangalam: '#a78bfa',
  shubham: '#22d3ee',
};

export default function RagaCard({ raga, onClick }) {
  return (
    <div className="raga-card" onClick={() => onClick?.(raga)}>
      <div className="raga-card-header">
        <div>
          <h3>{raga.name_english}</h3>
          {raga.name_telugu && (
            <p className="raga-telugu">{raga.name_telugu}</p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {raga.melakarta_number && (
            <span className="melakarta-badge">M{raga.melakarta_number}</span>
          )}
          {raga.janya_of && (
            <span className="janya-badge">Janya</span>
          )}
        </div>
      </div>

      <div className="raga-svaras">
        <div className="svara-row">
          <span className="svara-label">↑</span>
          <div className="svara-list">
            {raga.arohanam.map((s, i) => (
              <span key={i} className="svara-chip">{s}</span>
            ))}
          </div>
        </div>
        <div className="svara-row">
          <span className="svara-label">↓</span>
          <div className="svara-list">
            {raga.avarohanam.map((s, i) => (
              <span key={i} className="svara-chip">{s}</span>
            ))}
          </div>
        </div>
      </div>

      {raga.rasa_tags?.length > 0 && (
        <div className="rasa-tags">
          {raga.rasa_tags.map((tag) => (
            <span
              key={tag}
              className="rasa-tag"
              style={{ backgroundColor: RASA_COLORS[tag] || '#6b7280' }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="raga-card-footer">
        <span>Generate composition</span>
        <ChevronRight size={14} />
      </div>
    </div>
  );
}
