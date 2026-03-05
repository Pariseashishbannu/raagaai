import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listRagas, listTalas, submitGeneration } from '../api/client';
import { useJobPolling } from '../hooks/usePolling';
import ProgressTracker from '../components/ProgressTracker';
import AudioPlayer from '../components/AudioPlayer';
import SvaraDisplay from '../components/SvaraDisplay';
import {
  Sparkles, Music, RefreshCw, Layers, Clock, Type, Settings2,
  PlayCircle, Wand2, ChevronDown, ChevronUp, Mic2,
  Compass, MessageSquare, RotateCw, Download, Zap
} from 'lucide-react';

const SUGGESTION_CHIPS = [
  'Romantic love song in Mohanam',
  'Devotional song in Kalyani',
  'Upbeat celebration in Shankarabharanam',
  'Melancholy song in Kharaharapriya',
  'Nature-inspired melody in Hamsadhwani',
  'Soulful ballad in Begada',
];

export default function Generate() {
  const [searchParams] = useSearchParams();
  const [ragas, setRagas] = useState([]);
  const [talas, setTalas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [mode, setMode] = useState('simple'); // 'simple' | 'advanced'
  const [prompt, setPrompt] = useState('');
  const [showNotation, setShowNotation] = useState(false);

  const [form, setForm] = useState({
    raga_id: searchParams.get('raga') || 'mohanam',
    tala_id: 'adi',
    kala: 'madhyama',
    theme: 'romantic',
    sections: 3,
    structure: 'song',
    include_chittaswaram: false,
  });

  const { status } = useJobPolling(jobId);

  useEffect(() => {
    Promise.all([listRagas(), listTalas()])
      .then(([ragaRes, talaRes]) => {
        setRagas(ragaRes.data.ragas);
        setTalas(talaRes.data.talas);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const selectedRaga = ragas.find((r) => r.id === form.raga_id);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setJobId(null);
    try {
      const payload = mode === 'simple'
        ? { prompt, structure: 'song' }
        : { ...form };
      const res = await submitGeneration(payload);
      setJobId(res.data.job_id);
    } catch (err) {
      alert(err.response?.data?.detail || 'Generation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setJobId(null);
    setShowNotation(false);
  };

  const isComplete = status?.status === 'completed';
  const isFailed = status?.status === 'failed';
  const songTitle = status?.result?.song_title;

  return (
    <div className="generate-page animate-fade-in">
      <header className="page-header text-center">
        <div className="badge-wrapper mb-2">
          <span className="premium-badge">Neural Composer</span>
        </div>
        <h1>Forge Your Masterpiece</h1>
        <p>Harness celestial intelligence to weave authentic Carnatic melodies and soul-stirring Telugu sahityam.</p>
      </header>

      <div className="mode-toggle-wrapper">
        <div className="mode-toggle">
          <button
            className={`mode-btn ${mode === 'simple' ? 'active' : ''}`}
            onClick={() => setMode('simple')}
            disabled={status === 'processing'}
          >
            <Sparkles size={16} />
            Simple
          </button>
          <button
            className={`mode-btn ${mode === 'advanced' ? 'active' : ''}`}
            onClick={() => setMode('advanced')}
            disabled={status === 'processing'}
          >
            <Layers size={16} />
            Advanced
          </button>
        </div>
      </div>

      <div className="generate-layout">
        <aside className="generate-sidebar">
          <div className="glass-card generate-form-panel">
            <div className="panel-header">
              <Compass size={18} className="glow-icon" />
              <h3>Configurations</h3>
            </div>

            <div className="generate-form">
              <div className="form-group">
                <label>
                  <MessageSquare size={14} />
                  Creative Vision
                </label>
                <textarea
                  className="prompt-input"
                  placeholder="Describe your vision (e.g., A soulful morning raga about the beauty of Godavari...)"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={status === 'processing'}
                  rows={4}
                />
                <div className="suggestion-chips">
                  {SUGGESTION_CHIPS.map(s => (
                    <button
                      key={s}
                      className={`suggestion-chip ${prompt === s ? 'active' : ''}`}
                      onClick={() => setPrompt(s)}
                      disabled={status === 'processing'}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {mode === 'advanced' && (
                <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div className="form-group">
                    <label>
                      <Music size={14} />
                      Melodic Framework (Raga)
                    </label>
                    <select
                      value={form.raga_id}
                      onChange={(e) => setForm({ ...form, raga_id: e.target.value })}
                      disabled={status === 'processing'}
                    >
                      <option value="none">AI Recommended</option>
                      {ragas.map(r => <option key={r.id} value={r.id}>{r.name_english} ({r.name_telugu})</option>)}
                    </select>
                    {selectedRaga && (
                      <div className="raga-preview-glass animate-fade-in">
                        <div className="svara-viz">
                          <span className="label">Arohana</span>
                          <span className="svaras highlight">{selectedRaga.arohanam.join(' ')}</span>
                        </div>
                        <div className="svara-viz">
                          <span className="label">Avarohana</span>
                          <span className="svaras">{selectedRaga.avarohanam.join(' ')}</span>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="form-group">
                    <label>
                      <Clock size={14} />
                      Rhythmic Cycle (Tala)
                    </label>
                    <select
                      value={form.tala_id}
                      onChange={(e) => setForm({ ...form, tala_id: e.target.value })}
                      disabled={status === 'processing'}
                    >
                      <option value="none">AI Recommended</option>
                      {talas.map(t => <option key={t.id} value={t.id}>{t.name} ({t.beats} beats)</option>)}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>
                      <Zap size={14} />
                      Generation Depth
                    </label>
                    <div className="tab-group">
                      <button className="tab-btn active">Balanced</button>
                      <button className="tab-btn">Poetic</button>
                      <button className="tab-btn">Complex</button>
                    </div>
                  </div>
                </div>
              )}

              <button
                className="btn btn-primary btn-full btn-lg"
                onClick={handleSubmit}
                disabled={status === 'processing' || submitting || (mode === 'simple' && !prompt.trim())}
              >
                {submitting ? (
                  <><RotateCw className="spin" size={20} /> Generating...</>
                ) : (
                  <><Sparkles size={20} /> Ignite Creation</>
                )}
              </button>
            </div>
          </div>
        </aside>

        {/* Output Panel */}
        <main className="generate-main">
          <div className="glass-card generate-result-panel">
            {!jobId && !status && (
              <div className="result-placeholder">
                <div className="placeholder-icon">
                  <Mic2 size={36} />
                </div>
                <h3>Your song awaits</h3>
                <p>Describe the song you want to create, or configure the details manually.</p>
              </div>
            )}

            {jobId && status && !isComplete && !isFailed && (
              <div className="processing-state animate-fade-in">
                <ProgressTracker status={status} />
              </div>
            )}

            {isComplete && status.result && (
              <div className="result-content animate-slide-up">
                <div className="song-title-display">
                  <h2 className="song-title gradient-text">{songTitle || 'Celestial Composition'}</h2>
                </div>

                <div className="player-wrapper">
                  <AudioPlayer
                    src={status.result.audio_url}
                    title={songTitle || 'New Creation'}
                  />
                </div>

                <div className="result-sections">
                  <div className="lyrics-section">
                    <span className="lyrics-section-label">Telugu Sahityam</span>
                    <div className="lyrics-structured mt-3">
                      {status.result.sahityam_sections ? (
                        Object.entries(status.result.sahityam_sections).map(([section, text]) => (
                          <div key={section} className="lyrics-block">
                            <span className="lyrics-section-label">
                              {section.replace(/_/g, ' ')}
                            </span>
                            <p className="lyrics-text">{text}</p>
                          </div>
                        ))
                      ) : (
                        <div className="lyrics-block">
                          <p className="lyrics-text">{status.result.sahityam}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="svara-section">
                    <button
                      className="notation-toggle"
                      onClick={() => setShowNotation(!showNotation)}
                    >
                      <span className="flex items-center gap-2">
                        <Music size={18} />
                        {showNotation ? 'Hide' : 'View'} Musical Notation
                      </span>
                      <ChevronDown size={18} style={{ transform: showNotation ? 'rotate(180deg)' : 'none', transition: '0.3s' }} />
                    </button>

                    {showNotation && (
                      <div className="notation-content animate-fade-in">
                        <SvaraDisplay sequence={status.result.svara_sequence} />
                      </div>
                    )}
                  </div>

                  <div className="metadata-bar">
                    <div className="meta-capsule">
                      <span className="label">Raga</span>
                      <span className="value">{status.result.metadata?.raga_id || 'Recommended'}</span>
                    </div>
                    <div className="meta-capsule">
                      <span className="label">Tala</span>
                      <span className="value">{status.result.metadata?.tala_id || 'Classical'}</span>
                    </div>
                    <div className="meta-capsule">
                      <span className="label">Kala</span>
                      <span className="value">{status.result.metadata?.kala || 'Medium'}</span>
                    </div>
                    <button className="btn btn-outline ml-auto">
                      <Download size={18} />
                      Export
                    </button>
                  </div>
                </div>
              </div>
            )}

            {isFailed && <ProgressTracker status={status} />}
          </div>
        </main>
      </div>
    </div>
  );
}
