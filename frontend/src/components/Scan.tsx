import { useEffect, useRef, useState } from "react";
import { api, type Attempt, type Child, type GradeResult } from "../api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import Results from "./Results";

export default function Scan({ child }: { child: Child }) {
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [picked, setPicked] = useState<Attempt>();
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
      <div className="text-lg">Sheet <span className="font-mono font-bold">{picked.code}</span></div>
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
        <button key={a.id} onClick={() => setPicked(a)} className="text-left">
          <Card className="flex items-center justify-between">
            <span>Sheet <span className="font-mono font-bold">{a.code}</span></span>
            <span className="text-slate-500">{a.status}</span>
          </Card>
        </button>
      ))}
    </div>
  );
}
