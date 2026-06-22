import { useEffect, useRef, useState } from "react";
import { api, type AttemptListItem, type Child, type GradeResult } from "../api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import Results from "./Results";

export default function Scan({ child }: { child: Child }) {
  const [attempts, setAttempts] = useState<AttemptListItem[]>([]);
  const [picked, setPicked] = useState<AttemptListItem>();
  const [file, setFile] = useState<File>();
  const [tricky, setTricky] = useState(false);
  const [grading, setGrading] = useState(false);
  const [result, setResult] = useState<GradeResult>();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listAttempts(child.id)
      .then((a) => setAttempts(a.filter((x) => x.status !== "graded")))
      .catch(() => setAttempts([]));
  }, [child.id]);

  const grade = async () => {
    if (!picked || !file) return;
    setGrading(true);
    try { setResult(await api.uploadSubmission(child.id, picked.id, file, tricky)); }
    finally { setGrading(false); }
  };

  if (result) return (
    <div>
      <Button variant="ghost" onClick={() => { setResult(undefined); setPicked(undefined); setFile(undefined); }}>← Scan another</Button>
      <div className="mt-3"><Results result={result} /></div>
    </div>
  );

  if (picked) return (
    <div className="flex flex-col gap-3">
      <Button variant="ghost" onClick={() => setPicked(undefined)}>← Sheets</Button>
      <div>
        <div className="text-xl font-bold">{picked.worksheet_title}</div>
        <div className="text-slate-500">{picked.topic} · {picked.section} · sheet <span className="font-mono">{picked.code}</span></div>
        <a href={api.printUrl(picked.id)} target="_blank" rel="noopener" className="text-indigo-600 underline">Reprint sheet ↗</a>
      </div>
      <input ref={inputRef} data-testid="photo-input" type="file" accept="image/*" capture="environment"
        onChange={(e) => setFile(e.target.files?.[0])} />
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={tricky} onChange={(e) => setTricky(e.target.checked)} />
        Tricky section (use AI equivalence check)
      </label>
      <Button onClick={grade} disabled={!file || grading}>{grading ? "Reading your answers…" : "Grade"}</Button>
    </div>
  );

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xl font-bold">Sheets to scan</h2>
      {attempts.length === 0 && <div className="text-slate-500">Nothing to scan — print a sheet first.</div>}
      {attempts.map((a) => (
        <Card key={a.id} className="flex items-center justify-between gap-3">
          <button onClick={() => setPicked(a)} className="flex-1 text-left">
            <div className="font-semibold">{a.worksheet_title}</div>
            <div className="text-sm text-slate-500">{a.topic} · {a.section} · sheet <span className="font-mono">{a.code}</span></div>
          </button>
          <a href={api.printUrl(a.id)} target="_blank" rel="noopener"
             className="shrink-0 text-indigo-600 underline">Reprint ↗</a>
        </Card>
      ))}
    </div>
  );
}
