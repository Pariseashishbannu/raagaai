import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listRagas, listTalas } from '../api/client';
import RagaCard from '../components/RagaCard';
import { Search, Loader } from 'lucide-react';

export default function Explore() {
  const [ragas, setRagas] = useState([]);
  const [talas, setTalas] = useState([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([listRagas(), listTalas()])
      .then(([ragaRes, talaRes]) => {
        setRagas(ragaRes.data.ragas);
        setTalas(talaRes.data.talas);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = ragas.filter((r) => {
    const matchesSearch =
      r.name_english.toLowerCase().includes(search.toLowerCase()) ||
      r.id.toLowerCase().includes(search.toLowerCase()) ||
      (r.name_telugu && r.name_telugu.includes(search));

    const matchesFilter =
      filter === 'all' ||
      (filter === 'melakarta' && r.melakarta_number) ||
      (filter === 'janya' && r.janya_of);

    return matchesSearch && matchesFilter;
  });

  const handleRagaClick = (raga) => {
    navigate(`/generate?raga=${raga.id}`);
  };

  const melaCount = ragas.filter((r) => r.melakarta_number).length;
  const janyaCount = ragas.filter((r) => r.janya_of).length;

  return (
    <div className="explore-page animate-fade-in">
      <div className="page-header">
        <h1>Explore Ragas</h1>
        <p>Browse through {ragas.length} ragas from the Carnatic tradition</p>
      </div>

      <div className="explore-controls">
        <div className="search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by name, ID, or Telugu name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="filter-tabs">
          {[
            { key: 'all', label: `All (${ragas.length})` },
            { key: 'melakarta', label: `Melakarta (${melaCount})` },
            { key: 'janya', label: `Janya (${janyaCount})` },
          ].map((tab) => (
            <button
              key={tab.key}
              className={`filter-tab ${filter === tab.key ? 'active' : ''}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="loading">
          <Loader size={20} className="spin" style={{ display: 'inline-block', marginRight: 8 }} />
          Loading ragas...
        </div>
      ) : (
        <>
          <div className="raga-grid">
            {filtered.map((raga, i) => (
              <div key={raga.id} className="animate-fade-in" style={{ animationDelay: `${Math.min(i * 0.03, 0.3)}s` }}>
                <RagaCard raga={raga} onClick={handleRagaClick} />
              </div>
            ))}
          </div>
          {filtered.length === 0 && (
            <div className="empty-state">No ragas match your search.</div>
          )}
        </>
      )}

      {/* Tala Section */}
      <div className="tala-section">
        <h2>Supported Talas</h2>
        <div className="tala-grid">
          {talas.map((tala) => (
            <div key={tala.id} className="tala-card">
              <h3>{tala.name}</h3>
              <div className="tala-info">
                <span>{tala.beats} beats</span>
                <span>{tala.jathi}</span>
              </div>
              <div className="tala-structure">
                {tala.structure.map((s, i) => (
                  <span key={i} className="structure-chip">{s}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
