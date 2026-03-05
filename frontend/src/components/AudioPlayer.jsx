import { useState, useRef, useEffect } from 'react';
import { Play, Pause, Volume2, Download, RotateCcw } from 'lucide-react';

export default function AudioPlayer({ src, title }) {
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTime = () => setCurrentTime(audio.currentTime);
    const onMeta = () => setDuration(audio.duration);
    const onEnd = () => setPlaying(false);

    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('ended', onEnd);

    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('ended', onEnd);
    };
  }, [src]);

  const toggle = () => {
    if (playing) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setPlaying(!playing);
  };

  const restart = () => {
    audioRef.current.currentTime = 0;
    audioRef.current.play();
    setPlaying(true);
  };

  const seek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioRef.current.currentTime = pct * duration;
  };

  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="audio-player">
      <audio ref={audioRef} src={src} preload="metadata" />

      <div className="player-header">
        <Volume2 size={16} />
        <span className="player-title">{title || 'Composition'}</span>
      </div>

      <div className="player-controls">
        <button className="btn-icon" onClick={restart} title="Restart">
          <RotateCcw size={16} />
        </button>

        <button className="btn-play" onClick={toggle}>
          {playing ? <Pause size={22} /> : <Play size={22} style={{ marginLeft: 2 }} />}
        </button>

        <a href={src} download className="btn-icon" title="Download">
          <Download size={16} />
        </a>
      </div>

      <div className="player-progress" onClick={seek}>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-time">
          <span>{fmt(currentTime)}</span>
          <span>{fmt(duration)}</span>
        </div>
      </div>
    </div>
  );
}
