import { useState } from "react";
import type { GradeResult, ProblemResult } from "../api";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import Tutor from "./tutor/Tutor";

function Row({ r, onHelp }: { r: ProblemResult; onHelp: (() => void) | null }) {
  const blank = r.read_answer === null;
  return (
    <Card className="flex items-start justify-between">
      <div>
        <span className="font-bold">#{r.number}</span>{" "}
        {blank ? (
          <span className="text-slate-500">not attempted</span>
        ) : (
          <>
            <span className={r.is_correct ? "text-green-700" : "text-red-700"}>
              {r.is_correct ? "✓" : "✗"} you wrote {r.read_answer}
            </span>
            {!r.is_correct && r.correct_answer !== null && (
              <span className="ml-2 text-slate-700">· correct answer: {r.correct_answer}</span>
            )}
          </>
        )}
      </div>
      <div className="flex items-center gap-2">
        {r.needs_review && <span title="check this" className="text-amber-600">⚐</span>}
        {onHelp && <Button onClick={onHelp} className="px-2 py-1 text-sm">Get help</Button>}
      </div>
    </Card>
  );
}

export default function Results({ result, childId, attemptId }:
  { result: GradeResult; childId: string; attemptId: string }) {
  const [helpProblemId, setHelpProblemId] = useState<string | null>(null);
  const attempted = result.results.filter((r) => r.read_answer !== null).length;
  const pct = result.score_total ? Math.round((result.score_correct / result.score_total) * 100) : 0;
  const pctAttempted = attempted ? Math.round((result.score_correct / attempted) * 100) : 0;
  return (
    <div className="flex flex-col gap-3">
      <div>
        <div className="text-4xl font-extrabold">
          {result.score_correct}/{result.score_total}{" "}
          <span className="text-2xl font-bold text-slate-500">({pct}%)</span>
        </div>
        <div className="text-slate-600">
          Attempted {attempted} of {result.score_total} · {result.score_correct}/{attempted} correct
          {attempted ? ` (${pctAttempted}%)` : ""}
        </div>
      </div>
      {!result.identity_ok && <div className="text-amber-700">⚠ This photo's code didn't match — is it the right sheet?</div>}
      {result.results.map((r) => (
        <Row key={r.problem_id} r={r}
             onHelp={!r.is_correct && r.read_answer !== null ? () => setHelpProblemId(r.problem_id) : null} />
      ))}
      {helpProblemId && (
        <Tutor childId={childId} attemptId={attemptId} problemId={helpProblemId}
               onClose={() => setHelpProblemId(null)} />
      )}
    </div>
  );
}
