import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Scan from "./Scan";

afterEach(() => vi.restoreAllMocks());
const child = { id: "k1", name: "Ada", grade: 5, has_pin: false };

test("pick a printed attempt, upload a photo, see the score", async () => {
  vi.spyOn(global, "fetch").mockImplementation((url, init) => {
    const u = String(url);
    if (u === "/api/children/k1/attempts")
      return Promise.resolve(new Response(JSON.stringify([
        { id: "att1", code: "6Q4H7", child_id: "k1", worksheet_id: "w1", status: "printed",
          worksheet_title: "Adding", topic: "math", section: "Addition",
          printed_at: "t", scanned_at: null, graded_at: null },
      ]), { status: 200 }));
    if (u.endsWith("/submissions") && init?.method === "POST")
      return Promise.resolve(new Response(JSON.stringify({
        submission_id: "s", attempt_id: "att1", score_correct: 2, score_total: 2, needs_review_count: 0, identity_ok: true,
        results: [
          { problem_id: "p1", number: 1, read_answer: "4", is_correct: true, confidence: 1, match_method: "exact", needs_review: false, correct_answer: null },
          { problem_id: "p2", number: 2, read_answer: "6", is_correct: true, confidence: 1, match_method: "exact", needs_review: false, correct_answer: null },
        ],
      }), { status: 200 }));
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
  render(<Scan child={child} />);
  await userEvent.click(await screen.findByRole("button", { name: /6Q4H7/i }));
  const file = new File([new Uint8Array([1, 2, 3])], "photo.jpg", { type: "image/jpeg" });
  await userEvent.upload(screen.getByTestId("photo-input"), file);
  await userEvent.click(screen.getByRole("button", { name: /grade/i }));
  await waitFor(() => expect(screen.getByText(/Attempted 2 of 2/)).toBeInTheDocument());
});
