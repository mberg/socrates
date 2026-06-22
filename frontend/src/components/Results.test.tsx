import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Results from "./Results";
import type { GradeResult } from "../api";

const result: GradeResult = {
  submission_id: "s", attempt_id: "a", score_correct: 1, score_total: 3, needs_review_count: 0, identity_ok: true,
  results: [
    { problem_id: "p1", number: 1, read_answer: "4", is_correct: true, confidence: 1, match_method: "exact", needs_review: false, correct_answer: null },
    { problem_id: "p2", number: 2, read_answer: "7", is_correct: false, confidence: 1, match_method: "normalized", needs_review: false, correct_answer: "6" },
    { problem_id: "p3", number: 3, read_answer: null, is_correct: false, confidence: 0, match_method: "exact", needs_review: false, correct_answer: "10" },
  ],
};

test("shows score, the correct answer on attempted-wrong, and nothing on blanks", () => {
  render(<Results result={result} />);
  expect(screen.getByText("1/3")).toBeInTheDocument();
  // attempted-wrong row reveals the correct answer
  expect(screen.getByText(/correct answer:\s*6/i)).toBeInTheDocument();
  // blank row says not attempted and never shows an answer
  expect(screen.getByText(/not attempted/i)).toBeInTheDocument();
  expect(screen.queryByText(/correct answer:\s*10/i)).not.toBeInTheDocument();
});
