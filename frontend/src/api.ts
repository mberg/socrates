export interface Child { id: string; name: string; grade: number; has_pin: boolean }
export interface Skill { id: string; grade: number; topic: string; skill_key: string; label: string }
export interface Worksheet { id: string; skill_id: string; title: string; variant: string | null; problem_count: number; source_pdf_r2_key: string | null }
export interface Attempt { id: string; code: string | null; child_id: string; worksheet_id: string; status: string; printed_at: string | null; scanned_at: string | null; graded_at: string | null }
export interface ProblemResult { problem_id: string; number: number; read_answer: string | null; is_correct: boolean; confidence: number; match_method: string; needs_review: boolean; correct_answer: string | null }
export interface GradeResult { submission_id: string; attempt_id: string; score_correct: number; score_total: number; needs_review_count: number; identity_ok: boolean; results: ProblemResult[] }
export interface ScoreSummary { attempt_id: string; worksheet_title: string; score_correct: number; score_total: number; graded_at: string | null }

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  listChildren: () => fetch("/api/children").then(j<Child[]>),
  createChild: (name: string, grade: number, pin?: string) =>
    fetch("/api/children", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, grade, pin: pin || null }) }).then(j<Child>),
  verifyPin: (childId: string, pin: string) =>
    fetch(`/api/children/${childId}/verify-pin`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ pin }) }).then(j<{ ok: boolean }>),
  listSkills: (grade: number) => fetch(`/api/skills?grade=${grade}`).then(j<Skill[]>),
  listWorksheets: (skillId: string) => fetch(`/api/skills/${skillId}/worksheets`).then(j<Worksheet[]>),
  createAttempt: (childId: string, worksheetId: string) =>
    fetch(`/api/children/${childId}/attempts`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ worksheet_id: worksheetId }) }).then(j<Attempt>),
  listAttempts: (childId: string) => fetch(`/api/children/${childId}/attempts`).then(j<Attempt[]>),
  printUrl: (attemptId: string) => `/api/attempts/${attemptId}/print`,
  uploadSubmission: (childId: string, attemptId: string, file: File, aiFallback: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("ai_fallback", aiFallback ? "true" : "false");
    return fetch(`/api/children/${childId}/attempts/${attemptId}/submissions`, { method: "POST", body: fd }).then(j<GradeResult>);
  },
  getResults: (attemptId: string) => fetch(`/api/attempts/${attemptId}/results`).then(j<GradeResult>),
  getScores: (childId: string) => fetch(`/api/children/${childId}/scores`).then(j<ScoreSummary[]>),
};
