import { afterEach, expect, test, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.restoreAllMocks());

test("createChild posts name/grade/pin and parses the child", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: "x", name: "Ada", grade: 5, has_pin: true }), { status: 200 }),
  );
  const child = await api.createChild("Ada", 5, "1234");
  expect(child.has_pin).toBe(true);
  const [url, init] = spy.mock.calls[0];
  expect(url).toBe("/api/children");
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ name: "Ada", grade: 5, pin: "1234" });
});

test("j throws on non-ok", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 500 }));
  await expect(api.listChildren()).rejects.toThrow(/500/);
});

test("startGuidance posts to the nested problems route", async () => {
  const session = { id: "g1", problem_id: "p", problem_number: 3, problem_prompt: "3 x 4",
    max_tier_reached: 1, resolved: false, turns: [] };
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }));
  const out = await api.startGuidance("c", "a", "p");
  expect(out.id).toBe("g1");
  expect(spy).toHaveBeenCalledWith("/api/children/c/attempts/a/problems/p/guidance", { method: "POST" });
});

test("postTurn sends advance flag as JSON", async () => {
  const session = { id: "g1", problem_id: "p", problem_number: 3, problem_prompt: "3 x 4",
    max_tier_reached: 2, resolved: false, turns: [] };
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }));
  await api.postTurn("g1", { advance: true });
  expect(spy).toHaveBeenCalledWith("/api/guidance/g1/turns", expect.objectContaining({ method: "POST" }));
});
