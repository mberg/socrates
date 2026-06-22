export default function MultGrid({ rows, cols, partial }: { rows: number; cols: number; partial?: boolean }) {
  const r = Math.max(1, rows), c = Math.max(1, cols), cell = 22;
  return (
    <figure className="inline-block">
      <svg viewBox={`0 0 ${c * cell + 2} ${r * cell + 2}`} width={c * cell + 2} height={r * cell + 2}
           role="img" aria-label={`${r} by ${c} array`}>
        {Array.from({ length: r }, (_, ri) =>
          Array.from({ length: c }, (_, ci) => (
            <rect key={`${ri}-${ci}`} x={ci * cell + 1} y={ri * cell + 1} width={cell - 2} height={cell - 2}
                  fill="#bfdbfe" stroke="#3b82f6" />
          )))}
      </svg>
      {partial && <figcaption className="text-center text-sm text-slate-600">{r} × {c} = {r * c}</figcaption>}
    </figure>
  );
}
