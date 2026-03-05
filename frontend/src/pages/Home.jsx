import { Link } from 'react-router-dom';
import {
  Sparkles, Compass, Music, Zap, Layers, Mic2, ArrowRight,
  AudioLines, PenTool, Waves, Timer, Play, Volume2, ListMusic,
  Brain, Headphones, SlidersHorizontal, Cpu
} from 'lucide-react';

const FEATURES = [
  {
    icon: <Mic2 size={28} color="#fff" />,
    gradient: 'linear-gradient(135deg, #3b82f6, #a78bfa)',
    title: 'Vocal Synthesis',
    desc: 'High-fidelity Telugu vocal generation capturing the nuanced gamakas and microtonal expressions of Carnatic tradition.',
  },
  {
    icon: <Music size={28} color="#fff" />,
    gradient: 'linear-gradient(135deg, #f43f5e, #fb923c)',
    title: 'Raga Intelligence',
    desc: 'Deep understanding of 80+ ragas — every melodic phrase follows authentic arohanam, avarohanam, and ornamentation rules.',
  },
  {
    icon: <Layers size={28} color="#fff" />,
    gradient: 'linear-gradient(135deg, #22d3ee, #3b82f6)',
    title: 'Rhythmic Precision',
    desc: 'Authentic mridangam and percussion patterns aligned to the seven foundational talas of Carnatic music.',
  },
  {
    icon: <Sparkles size={28} color="#fff" />,
    gradient: 'linear-gradient(135deg, #6366f1, #a78bfa)',
    title: 'Sahityam Generation',
    desc: 'Context-aware Telugu lyric composition weaving classical devotional themes with contemporary poetic sensibility.',
  },
];

const STATS = [
  { num: '87+', label: 'Ragas' },
  { num: '7', label: 'Talas' },
  { num: '5', label: 'Themes' },
  { num: 'AI', label: 'Powered' },
];

export default function Home() {
  return (
    <div className="home">
      {/* Hero */}
      <section className="hero">
        {/* Floating orbs */}
        <div className="hero-orb hero-orb--sapphire" />
        <div className="hero-orb hero-orb--rose" />
        <div className="hero-orb hero-orb--lavender" />

        <div className="badge-wrapper animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <span className="premium-badge">Next-Gen Carnatic AI</span>
        </div>
        <h1 className="gradient-text animate-fade-in" style={{ animationDelay: '0.2s' }}>
          Where Tradition <br />Meets Tomorrow
        </h1>
        <p className="hero-subtitle animate-fade-in" style={{ animationDelay: '0.35s' }}>
          The first AI platform dedicated to the soul of Telugu musical heritage.
          Compose melodies, lyrics, and full productions — from raga to recording.
        </p>
        <div className="hero-actions animate-fade-in" style={{ animationDelay: '0.5s' }}>
          <Link to="/generate" className="btn btn-primary btn-lg">
            <Sparkles size={20} />
            Start Composing
          </Link>
          <Link to="/explore" className="btn btn-outline btn-lg">
            <Compass size={20} />
            Explore Ragas
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="features-section">
        <div className="section-header">
          <h2 className="section-title">How It Works</h2>
          <p className="section-subtitle">
            From a simple text prompt to a complete Telugu composition — melody, rhythm, lyrics, and audio.
          </p>
        </div>

        <div className="feature-grid">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="feature-card animate-fade-in"
              style={{ animationDelay: `${0.1 + i * 0.08}s` }}
            >
              <div className="feature-icon" style={{ background: f.gradient }}>
                {f.icon}
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* AI Song Production */}
      <section className="generation-section">
        <div className="section-header">
          <span className="section-overline animate-fade-in">AI-Powered Music Production</span>
          <h2 className="section-title animate-fade-in" style={{ animationDelay: '0.05s' }}>
            Full Songs. Every Instrument. One Click.
          </h2>
          <p className="section-subtitle animate-fade-in" style={{ animationDelay: '0.1s' }}>
            Not just melodies — Raaga.AI produces complete, studio-quality Carnatic songs with
            AI-synthesized vocals, mridangam percussion, harmonic bass, tambura drone, and Telugu lyrics.
          </p>
        </div>

        {/* DAW-style production card */}
        <div className="production-card animate-fade-in" style={{ animationDelay: '0.15s' }}>
          <div className="production-header">
            <div className="production-header-left">
              <div className="production-status-dot" />
              <span className="production-label">AI Production Engine</span>
            </div>
            <div className="production-header-right">
              <span className="production-tag">SvaraTransformer</span>
              <span className="production-tag">WaveRNN Vocoder</span>
              <span className="production-tag">44.1 kHz</span>
            </div>
          </div>

          {/* Multi-track mixer */}
          <div className="mixer-tracks">
            {[
              { name: 'Vocal Melody', tech: 'Additive Synth + Formant Filter + ADSR', pct: 45, color: '#a78bfa', icon: <Mic2 size={15} /> },
              { name: 'Mridangam & Percussion', tech: '7 Talas · Stress Patterns · Beat Grid', pct: 25, color: '#f43f5e', icon: <AudioLines size={15} /> },
              { name: 'Harmonic Bass', tech: 'Octave-Dropped Melody · Smooth Envelope', pct: 18, color: '#3b82f6', icon: <Waves size={15} /> },
              { name: 'Tambura Drone', tech: 'Continuous Harmonic Resonance', pct: 12, color: '#10b981', icon: <Music size={15} /> },
              { name: 'Telugu Sahityam', tech: 'Syllable-Aligned Lyrics · 5 Themes', pct: null, color: '#fb923c', icon: <PenTool size={15} /> },
            ].map((track, i) => (
              <div key={track.name} className="mixer-track" style={{ animationDelay: `${0.2 + i * 0.06}s` }}>
                <div className="mixer-track-icon" style={{ color: track.color }}>
                  {track.icon}
                </div>
                <div className="mixer-track-info">
                  <div className="mixer-track-name">{track.name}</div>
                  <div className="mixer-track-tech">{track.tech}</div>
                </div>
                {track.pct !== null ? (
                  <div className="mixer-track-level">
                    <div className="mixer-level-bar">
                      <div
                        className="mixer-level-fill"
                        style={{ width: `${track.pct}%`, background: track.color }}
                      />
                    </div>
                    <span className="mixer-level-pct" style={{ color: track.color }}>{track.pct}%</span>
                  </div>
                ) : (
                  <div className="mixer-track-badge">Lyrics</div>
                )}
              </div>
            ))}
          </div>

          {/* Song structure timeline */}
          <div className="song-timeline">
            <div className="timeline-label">Song Structure</div>
            <div className="timeline-bar">
              {[
                { name: 'Intro', width: 10, color: 'rgba(167, 139, 250, 0.3)' },
                { name: 'Pallavi', width: 25, color: 'rgba(99, 102, 241, 0.4)' },
                { name: 'Anupallavi', width: 25, color: 'rgba(59, 130, 246, 0.4)' },
                { name: 'Charanam', width: 30, color: 'rgba(244, 63, 94, 0.35)' },
                { name: 'Outro', width: 10, color: 'rgba(16, 185, 129, 0.3)' },
              ].map((seg) => (
                <div
                  key={seg.name}
                  className="timeline-segment"
                  style={{ width: `${seg.width}%`, background: seg.color }}
                >
                  <span>{seg.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AI & ML capabilities */}
        <div className="ai-capabilities">
          {[
            {
              icon: <Brain size={24} />,
              gradient: 'linear-gradient(135deg, #6366f1, #a78bfa)',
              title: 'SvaraTransformer Neural Model',
              desc: 'A 1.5M-parameter GPT-2 style Transformer trained on Carnatic compositions — generates authentic svara sequences with raga-constrained decoding.',
            },
            {
              icon: <Headphones size={24} />,
              gradient: 'linear-gradient(135deg, #3b82f6, #22d3ee)',
              title: 'WaveRNN Neural Vocoder',
              desc: 'Converts synthesized audio into natural-sounding vocals through mel-spectrogram reconstruction — studio-quality voice output.',
            },
            {
              icon: <SlidersHorizontal size={24} />,
              gradient: 'linear-gradient(135deg, #f43f5e, #fb923c)',
              title: 'Gamaka-Aware Pitch Rendering',
              desc: 'Every note gets authentic Carnatic ornamentation — oscillations, slides, and microtonal bends rendered as real-time pitch contours.',
            },
            {
              icon: <Cpu size={24} />,
              gradient: 'linear-gradient(135deg, #10b981, #34d399)',
              title: 'Intelligent Multi-Track Mixing',
              desc: 'Section-aware dynamic mixing with ADSR envelopes, per-section gain curves, automatic normalization, and smooth crossfades.',
            },
          ].map((cap, i) => (
            <div
              key={cap.title}
              className="ai-cap-card animate-fade-in"
              style={{ animationDelay: `${0.25 + i * 0.08}s` }}
            >
              <div className="ai-cap-icon" style={{ background: cap.gradient }}>
                {cap.icon}
              </div>
              <h4>{cap.title}</h4>
              <p>{cap.desc}</p>
            </div>
          ))}
        </div>

        <div className="generation-cta animate-fade-in" style={{ animationDelay: '0.5s' }}>
          <Link to="/generate" className="btn btn-primary btn-lg">
            <Sparkles size={20} />
            Produce a Song
          </Link>
          <Link to="/explore" className="btn btn-outline btn-lg">
            <Compass size={20} />
            Explore Ragas
          </Link>
        </div>
      </section>

      {/* Stats */}
      <section className="stats">
        {STATS.map((s) => (
          <div key={s.label} className="stat">
            <div className="stat-num">{s.num}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </section>
    </div>
  );
}
