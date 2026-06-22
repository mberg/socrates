import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Results from "./Results";
import { api } from "../api";
import type { GradeResult } from "../api";

afterEach(() => vi.restoreAllMocks());

const result: GradeResult = {
  submission_id: "s", attempt_id: "a", score_correct: 1, score_total: 3, needs_review_count: 0, identity_ok: true,
  results: [
    { problem_id: "p1", number: 1, read_answer: "4", is_correct: true, confidence: 1, match_method: "exact", needs_review: false, correct_answer: null },
    { problem_id: "p2", number: 2, read_answer: "7", is_correct: false, confidence: 1, match_method: "normalized", needs_review: false, correct_answer: "6" },
    { problem_id: "p3", number: 3, read_answer: null, is_correct: false, confidence: 0, match_method: "exact", needs_review: false, correct_answer: "10" },
  ],
};

test("shows score, the correct answer on attempted-wrong, and nothing on blanks", () => {
  render(<Results result={result} childId="c" attemptId="a" />);
  expect(screen.getByText("1/3")).toBeInTheDocument();
  // attempted-wrong row reveals the correct answer
  expect(screen.getByText(/correct answer:\s*6/i)).toBeInTheDocument();
  // blank row says not attempted and never shows an answer
  expect(screen.getByText(/not attempted/i)).toBeInTheDocument();
  expect(screen.queryByText(/correct answer:\s*10/i)).not.toBeInTheDocument();
});

test("shows a Get help button on attempted-wrong rows and opens the tutor", async () => {
  vi.spyOn(api, "startGuidance").mockResolvedValue({ id: "g", problem_id: "p2", problem_number: 2,
    problem_prompt: "3+3", max_tier_reached: 1, resolved: false, turns: [] });
  render(<Results result={result} childId="c" attemptId="a" />);
  const help = screen.getAllByRole("button", { name: /get help/i });
  expect(help.length).toBe(1); // only the one attempted-wrong row (#2), not the blank (#3) or correct (#1)
  await userEvent.click(help[0]);
  expect(await screen.findByRole("dialog", { name: /tutor/i })).toBeInTheDocument();
});
