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
