import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import NumberLine from "./NumberLine";

test("renders whole-number tick labels even when ticks doesn't divide the range", () => {
  // Model sent ticks=11 over a range of 10 → naive division gives -4.09, -3.18, ...
  const { container } = render(
    <NumberLine min={-5} max={5} ticks={11} marks={[{ value: 3, label: "Start" }]} jumps={[{ from: 3, to: -4 }]} />,
  );
  const labels = Array.from(container.querySelectorAll("text")).map((t) => t.textContent ?? "");
  // No fractional tick labels like "-4.09"
  expect(labels.some((t) => /\d\.\d/.test(t))).toBe(false);
  // Clean integer ticks are present
  expect(labels).toContain("-5");
  expect(labels).toContain("0");
  expect(labels).toContain("5");
});
