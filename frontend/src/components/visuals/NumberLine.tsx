type Mark = { value: number; label?: string | null; color?: string | null };
type Jump = { from: number; to: number; label?: string | null };

// Snap to a "nice" step (1, 2, 2.5, 5, 10, …) so tick labels land on clean numbers
// regardless of how many ticks the model asks for (it often picks a count that doesn't
// divide the range, e.g. 11 ticks over a span of 10 → 0.909 steps → -4.09, -3.18, …).
function niceStep(range: number, target: number): number {
  if (range <= 0) return 1;
  const rough = range / Math.max(1, target);
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (m * pow >= rough) return m * pow;
  }
  return 10 * pow;
}

export default function NumberLine(
  { min, max, ticks, marks = [], jumps = [] }:
  { min: number; max: number; ticks?: number | null; marks?: Mark[]; jumps?: Jump[] }
) {
  const W = 320, H = 80, pad = 16;
  const x = (v: number) => pad + ((v - min) / (max - min || 1)) * (W - 2 * pad);
  const range = Math.max(0, max - min);
  const target = ticks && ticks > 0 ? ticks : Math.min(10, Math.max(1, Math.round(range)));
  const step = niceStep(range, target);
  const tickVals: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) {
    tickVals.push(Math.round(v / step) * step);
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-md" role="img" aria-label="number line">
      <line x1={pad} y1={50} x2={W - pad} y2={50} stroke="#334155" strokeWidth={2} />
      {tickVals.map((v, i) => (
        <g key={i}>
          <line x1={x(v)} y1={45} x2={x(v)} y2={55} stroke="#334155" />
          <text x={x(v)} y={70} textAnchor="middle" fontSize={9} fill="#64748b">{+v.toFixed(2)}</text>
        </g>
      ))}
      {jumps.map((j, i) => (
        <path key={`j${i}`} d={`M ${x(j.from)} 40 Q ${(x(j.from) + x(j.to)) / 2} 12 ${x(j.to)} 40`}
              fill="none" stroke="#2563eb" strokeWidth={1.5} markerEnd="url(#arrow)" />
      ))}
      {marks.map((m, i) => (
        <g key={`m${i}`}>
          <circle cx={x(m.value)} cy={50} r={4} fill={m.color || "#dc2626"} />
          {m.label && <text x={x(m.value)} y={34} textAnchor="middle" fontSize={10} fill="#0f172a">{m.label}</text>}
        </g>
      ))}
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#2563eb" />
        </marker>
      </defs>
    </svg>
  );
}
