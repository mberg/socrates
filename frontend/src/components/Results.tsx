import type { GradeResult, ProblemResult } from "../api";
import { Card } from "./ui/Card";

function Row({ r }: { r: ProblemResult }) {
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
      {r.needs_review && <span title="check this" className="text-amber-600">⚐</span>}
    </Card>
  );
}

export default function Results({ result }: { result: GradeResult }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="text-4xl font-extrabold">{result.score_correct}/{result.score_total}</div>
      {!result.identity_ok && <div className="text-amber-700">⚠ This photo's code didn't match — is it the right sheet?</div>}
      {result.results.map((r) => <Row key={r.problem_id} r={r} />)}
    </div>
  );
}
