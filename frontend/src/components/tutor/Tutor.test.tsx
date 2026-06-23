import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Tutor from "./Tutor";
import { api } from "../../api";
import type { GuidanceSession } from "../../api";

afterEach(() => vi.restoreAllMocks());

const tier1: GuidanceSession = {
  id: "g1", problem_id: "p", problem_number: 3, problem_prompt: "3 x 4",
  max_tier_reached: 1, resolved: false,
  turns: [{ id: "t1", role: "tutor", text: "What operation?", input_source: null,
            visuals: [{ type: "math", tex: "3 \\times 4" }], tier: 1, created_at: "" }],
};
const tier3: GuidanceSession = {
  ...tier1, max_tier_reached: 3,
  turns: [...tier1.turns, { id: "t2", role: "tutor", text: "The answer is 12.",
    input_source: null, visuals: [], tier: 3, created_at: "" }],
};

test("loads the opening turn and renders its visual", async () => {
  vi.spyOn(api, "startGuidance").mockResolvedValue(tier1);
  render(<Tutor childId="c" attemptId="a" problemId="p" onClose={() => {}} />);
  expect(await screen.findByText("What operation?")).toBeInTheDocument();
});

test("'show me more' advances and reveals the Tier-3 answer", async () => {
  vi.spyOn(api, "startGuidance").mockResolvedValue(tier1);
  const post = vi.spyOn(api, "postTurn").mockResolvedValue(tier3);
  render(<Tutor childId="c" attemptId="a" problemId="p" onClose={() => {}} />);
  await screen.findByText("What operation?");
  await userEvent.click(screen.getByRole("button", { name: /show me more/i }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("g1", { advance: true }));
  expect(await screen.findByText(/the answer is 12/i)).toBeInTheDocument();
});

test("'Show me the answer' jumps straight to Tier 3 and reveals", async () => {
  vi.spyOn(api, "startGuidance").mockResolvedValue(tier1);
  const post = vi.spyOn(api, "postTurn").mockResolvedValue(tier3);
  render(<Tutor childId="c" attemptId="a" problemId="p" onClose={() => {}} />);
  await screen.findByText("What operation?");
  await userEvent.click(screen.getByRole("button", { name: /show me the answer/i }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("g1", { reveal: true }));
  expect(await screen.findByText(/the answer is 12/i)).toBeInTheDocument();
});

test("'Show me the answer' stays clickable at Tier 3 (show me more is disabled)", async () => {
  vi.spyOn(api, "startGuidance").mockResolvedValue(tier3);
  const post = vi.spyOn(api, "postTurn").mockResolvedValue(tier3);
  render(<Tutor childId="c" attemptId="a" problemId="p" onClose={() => {}} />);
  await screen.findByText(/the answer is 12/i);
  expect(screen.getByRole("button", { name: /show me more/i })).toBeDisabled();
  const reveal = screen.getByRole("button", { name: /show me the answer/i });
  expect(reveal).toBeEnabled();
  await userEvent.click(reveal);
  await waitFor(() => expect(post).toHaveBeenCalledWith("g1", { reveal: true }));
});

test("'Got it' resolves the session and closes the tutor", async () => {
  vi.spyOn(api, "startGuidance").mockResolvedValue(tier1);
  const resolveSpy = vi.spyOn(api, "resolveGuidance").mockResolvedValue({ ...tier1, resolved: true });
  const onClose = vi.fn();
  render(<Tutor childId="c" attemptId="a" problemId="p" onClose={onClose} />);
  await screen.findByText("What operation?");
  await userEvent.click(screen.getByRole("button", { name: /got it/i }));
  await waitFor(() => expect(resolveSpy).toHaveBeenCalledWith("g1"));
  await waitFor(() => expect(onClose).toHaveBeenCalled());
});
