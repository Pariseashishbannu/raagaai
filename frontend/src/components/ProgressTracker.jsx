import { CheckCircle, Loader, Circle } from 'lucide-react';

const STAGES = [
  { key: 'setting_up_raga', label: 'Setting Up Raga', icon: '🎵' },
  { key: 'composing_melody', label: 'Composing Melody', icon: '🎼' },
  { key: 'writing_lyrics', label: 'Writing Telugu Lyrics', icon: '📝' },
  { key: 'producing_audio', label: 'Producing Audio & Beats', icon: '🥁' },
  { key: 'performing', label: 'Singing with Realistic Vocals', icon: '🎤' },
  { key: 'uploading', label: 'Finalizing Song', icon: '✨' },
];

export default function ProgressTracker({ status }) {
  if (!status) return null;

  const currentStage = status.stage;
  const progress = status.progress || 0;
  const currentIdx = STAGES.findIndex((s) => s.key === currentStage);

  const headerText =
    status.status === 'completed' ? 'Your Song is Ready!' :
    status.status === 'failed' ? 'Song Creation Failed' :
    status.status === 'queued' ? 'Waiting in Queue...' :
    'Creating Your Song...';

  return (
    <div className="progress-tracker">
      <div className="progress-header">
        <h3>{headerText}</h3>
        <div className="progress-pct">{Math.round(progress * 100)}%</div>
      </div>

      <div className="progress-bar-large">
        <div
          className={`progress-fill-large ${status.status === 'failed' ? 'error' : ''}`}
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      <div className="stage-list">
        {STAGES.map((stage, idx) => {
          const isDone = idx < currentIdx || status.status === 'completed';
          const isCurrent = idx === currentIdx && status.status === 'processing';

          return (
            <div
              key={stage.key}
              className={`stage-item ${isDone ? 'done' : ''} ${isCurrent ? 'current' : ''}`}
            >
              <span className="stage-icon">
                {isDone ? <CheckCircle size={16} /> :
                 isCurrent ? <Loader size={16} className="spin" /> :
                 <Circle size={16} />}
              </span>
              <span className="stage-emoji">{stage.icon}</span>
              <span className="stage-label">{stage.label}</span>
            </div>
          );
        })}
      </div>

      {status.error && (
        <div className="error-message" style={{ marginTop: '1rem' }}>
          <strong>Error:</strong> {status.error}
        </div>
      )}
    </div>
  );
}
