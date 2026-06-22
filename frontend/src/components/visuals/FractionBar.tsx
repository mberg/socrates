type Bar = { denominator: number; shaded: number; label?: string | null };
export default function FractionBar({ bars }: { bars: Bar[] }) {
  const W = 280, h = 28, gap = 10;
  return (
    <svg viewBox={`0 0 ${W} ${(h + gap) * bars.length}`} className="w-full max-w-sm" role="img" aria-label="fraction bars">
      {bars.map((b, bi) => {
        const d = Math.max(1, b.denominator), cell = W / d, y = bi * (h + gap);
        return (
          <g key={bi}>
            {Array.from({ length: d }, (_, i) => (
              <rect key={i} x={i * cell} y={y} width={cell - 1} height={h}
                    fill={i < b.shaded ? "#3b82f6" : "#e2e8f0"} stroke="#94a3b8" />
            ))}
            {b.label && <text x={4} y={y + h + 9} fontSize={10} fill="#475569">{b.label}</text>}
          </g>
        );
      })}
    </svg>
  );
}
