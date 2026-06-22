import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Home from "./Home";

afterEach(() => vi.restoreAllMocks());

function mockChildren(children: unknown[]) {
  vi.spyOn(global, "fetch").mockImplementation((url) => {
    if (String(url) === "/api/children") return Promise.resolve(new Response(JSON.stringify(children), { status: 200 }));
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
}

test("no-PIN kid enters immediately on tap", async () => {
  mockChildren([{ id: "k1", name: "Ada", grade: 5, has_pin: false }]);
  const onEnter = vi.fn();
  render(<Home onEnter={onEnter} />);
  const tile = await screen.findByRole("button", { name: /ada/i });
  await userEvent.click(tile);
  await waitFor(() => expect(onEnter).toHaveBeenCalledWith(expect.objectContaining({ id: "k1" })));
});

test("PIN kid must enter correct PIN before entering", async () => {
  vi.spyOn(global, "fetch").mockImplementation((url, init) => {
    const u = String(url);
    if (u === "/api/children") return Promise.resolve(new Response(JSON.stringify([{ id: "k2", name: "Bo", grade: 3, has_pin: true }]), { status: 200 }));
    if (u.endsWith("/verify-pin")) {
      const pin = JSON.parse((init as RequestInit).body as string).pin;
      return Promise.resolve(new Response(JSON.stringify({ ok: pin === "1234" }), { status: 200 }));
    }
    return Promise.resolve(new Response("{}", { status: 200 }));
  });
  const onEnter = vi.fn();
  render(<Home onEnter={onEnter} />);
  await userEvent.click(await screen.findByRole("button", { name: /bo/i }));
  for (const d of "9999") await userEvent.click(screen.getByRole("button", { name: d }));
  await waitFor(() => expect(screen.getByText(/try again/i)).toBeInTheDocument());
  expect(onEnter).not.toHaveBeenCalled();
  for (const d of "1234") await userEvent.click(screen.getByRole("button", { name: d }));
  await waitFor(() => expect(onEnter).toHaveBeenCalledWith(expect.objectContaining({ id: "k2" })));
});
