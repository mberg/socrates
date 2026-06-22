import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Scores from "./Scores";

afterEach(() => vi.restoreAllMocks());
const child = { id: "k1", name: "Ada", grade: 5, has_pin: false };

test("lists graded sheets and opens detail", async () => {
  vi.spyOn(global, "fetch").mockImplementation((url) => {
    const u = String(url);
    if (u === "/api/children/k1/scores")
      return Promise.resolve(new Response(JSON.stringify([
        { attempt_id: "att1", worksheet_title: "Adding", score_correct: 7, score_total: 10, graded_at: "2026-06-22T20:00:00" },
      ]), { status: 200 }));
    if (u === "/api/attempts/att1/results")
      return Promise.resolve(new Response(JSON.stringify({
        submission_id: "s", attempt_id: "att1", score_correct: 7, score_total: 10, needs_review_count: 0, identity_ok: true, results: [],
      }), { status: 200 }));
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
  render(<Scores child={child} />);
  await userEvent.click(await screen.findByRole("button", { name: /adding.*7\/10/i }));
  await waitFor(() => expect(screen.getByText("7/10")).toBeInTheDocument());
});
