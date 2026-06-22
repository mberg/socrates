import Prose from "../tutor/Prose";
export default function Steps({ title, steps }: { title?: string | null; steps: { text: string; highlight?: boolean }[] }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      {title && <div className="mb-1 font-bold">{title}</div>}
      <ol className="list-decimal pl-5">
        {steps.map((s, i) => (
          <li key={i} className={s.highlight ? "rounded bg-amber-100 px-1" : ""}><Prose text={s.text} /></li>
        ))}
      </ol>
    </div>
  );
}
