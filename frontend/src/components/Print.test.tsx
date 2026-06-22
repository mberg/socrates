import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Print from "./Print";

afterEach(() => vi.restoreAllMocks());

const child = { id: "k1", name: "Ada", grade: 5, has_pin: false };

function mockApi() {
  vi.spyOn(global, "fetch").mockImplementation((url, init) => {
    const u = String(url);
    if (u === "/api/skills?grade=5")
      return Promise.resolve(new Response(JSON.stringify([{ id: "s1", grade: 5, topic: "geometry", skill_key: "area", label: "Area" }]), { status: 200 }));
    if (u === "/api/skills/s1/worksheets")
      return Promise.resolve(new Response(JSON.stringify([{ id: "w1", skill_id: "s1", title: "Area A", variant: "a", problem_count: 10, source_pdf_r2_key: "x" }]), { status: 200 }));
    if (u === "/api/children/k1/attempts" && init?.method === "POST")
      return Promise.resolve(new Response(JSON.stringify({ id: "att1", code: "6Q4H7", child_id: "k1", worksheet_id: "w1", status: "printed", printed_at: "t", scanned_at: null, graded_at: null }), { status: 200 }));
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
}

test("browse to a worksheet and print opens the print URL", async () => {
  mockApi();
  const open = vi.spyOn(window, "open").mockReturnValue(null);
  render(<Print child={child} />);
  await userEvent.click(await screen.findByRole("button", { name: /geometry/i }));
  await userEvent.click(await screen.findByRole("button", { name: /area$/i }));
  await userEvent.click(await screen.findByRole("button", { name: /area a/i }));
  await userEvent.click(await screen.findByRole("button", { name: /print/i }));
  await waitFor(() => expect(open).toHaveBeenCalledWith("/api/attempts/att1/print", "_blank"));
});
