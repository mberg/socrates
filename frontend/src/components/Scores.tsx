import { useEffect, useState } from "react";
import { api, type Child, type GradeResult, type ScoreSummary } from "../api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import Results from "./Results";

function pct(correct: number, total: number) {
  return total ? Math.round((correct / total) * 100) : 0;
}

export default function Scores({ child }: { child: Child }) {
  const [rows, setRows] = useState<ScoreSummary[]>([]);
  const [selected, setSelected] = useState<ScoreSummary>();
  const [detail, setDetail] = useState<GradeResult>();

  useEffect(() => { api.getScores(child.id).then(setRows).catch(() => setRows([])); }, [child.id]);

  const open = (r: ScoreSummary) => { setSelected(r); api.getResults(r.attempt_id).then(setDetail); };

  if (detail && selected) return (
    <div>
      <Button variant="ghost" onClick={() => { setDetail(undefined); setSelected(undefined); }}>← My scores</Button>
      <div className="mt-3">
        <h2 className="text-2xl font-bold">{selected.worksheet_title}</h2>
        <div className="mb-4 text-slate-500">
          {selected.section} · sheet <span className="font-mono">{selected.code ?? selected.attempt_id.slice(0, 8)}</span>
          {selected.graded_at ? ` · ${selected.graded_at.slice(0, 10)}` : ""}
        </div>
        <Results result={detail} />
      </div>
    </div>
  );

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xl font-bold">My scores</h2>
      {rows.length === 0 && <div className="text-slate-500">No graded sheets yet.</div>}
      {rows.map((r) => (
        <button key={r.attempt_id} onClick={() => open(r)} className="text-left">
          <Card className="flex items-center justify-between gap-3">
            <div>
              <div className="font-semibold">{r.worksheet_title}</div>
              <div className="text-sm text-slate-500">
                {r.score_correct}/{r.score_total} ({pct(r.score_correct, r.score_total)}%)
                {" · "}{r.score_attempted} attempted
              </div>
            </div>
            <span className="shrink-0 text-slate-500">{r.graded_at ? r.graded_at.slice(0, 10) : ""}</span>
          </Card>
        </button>
      ))}
    </div>
  );
}
