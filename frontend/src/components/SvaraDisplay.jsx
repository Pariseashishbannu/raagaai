const SVARA_COLORS = {
  Sa: '#f43f5e',
  Ri1: '#fb923c', Ri2: '#fb923c',
  Ga1: '#fbbf24', Ga2: '#fbbf24',
  Ma1: '#22d3ee', Ma2: '#06b6d4',
  Pa: '#3b82f6',
  Da1: '#a78bfa', Da2: '#a78bfa',
  Ni1: '#fb7185', Ni2: '#fb7185',
};

export default function SvaraDisplay({ svaras, beatsPerLine = 8 }) {
  if (!svaras || svaras.length === 0) return null;

  const lines = [];
  for (let i = 0; i < svaras.length; i += beatsPerLine) {
    lines.push(svaras.slice(i, i + beatsPerLine));
  }

  return (
    <div className="svara-display">
      {lines.map((line, li) => (
        <div key={li} className="svara-line">
          <span className="line-num">{li + 1}</span>
          {line.map((s, si) => (
            <span
              key={si}
              className="svara-note"
              style={{ color: SVARA_COLORS[s] || '#8896a8' }}
            >
              {s}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
