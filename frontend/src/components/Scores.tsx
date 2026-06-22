import { useEffect, useState } from "react";
import { api, type Child, type GradeResult, type ScoreSummary } from "../api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import Results from "./Results";

export default function Scores({ child }: { child: Child }) {
  const [rows, setRows] = useState<ScoreSummary[]>([]);
  const [detail, setDetail] = useState<GradeResult>();

  useEffect(() => { api.getScores(child.id).then(setRows).catch(() => setRows([])); }, [child.id]);

  if (detail) return (
    <div>
      <Button variant="ghost" onClick={() => setDetail(undefined)}>← My scores</Button>
      <div className="mt-3"><Results result={detail} /></div>
    </div>
  );

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xl font-bold">My scores</h2>
      {rows.length === 0 && <div className="text-slate-500">No graded sheets yet.</div>}
      {rows.map((r) => (
        <button key={r.attempt_id} onClick={() => api.getResults(r.attempt_id).then(setDetail)} className="text-left">
          <Card className="flex items-center justify-between">
            <span>{r.worksheet_title} · {r.score_correct}/{r.score_total}</span>
            <span className="text-slate-500">{r.graded_at ? r.graded_at.slice(0, 10) : ""}</span>
          </Card>
        </button>
      ))}
    </div>
  );
}
