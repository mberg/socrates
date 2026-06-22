import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import VisualRenderer from "./VisualRenderer";
import type { Visual } from "./types";

const samples: Visual[] = [
  { type: "math", tex: "\\frac{1}{2}", display: true },
  { type: "steps", title: "Steps", steps: [{ text: "First" }, { text: "Then", highlight: true }] },
  { type: "number_line", min: 0, max: 10, ticks: 10, marks: [{ value: 7, label: "7" }] },
  { type: "fraction_bar", bars: [{ denominator: 4, shaded: 3 }] },
  { type: "place_value", value: 342 },
  { type: "mult_grid", rows: 3, cols: 4, partial: true },
];

test("renders each of the Core 6 without crashing", () => {
  for (const v of samples) {
    const { container } = render(<VisualRenderer visual={v} />);
    expect(container.firstChild).not.toBeNull();
  }
});

test("renders nothing for an unknown type", () => {
  const { container } = render(<VisualRenderer visual={{ type: "bogus" } as unknown as Visual} />);
  expect(container.firstChild).toBeNull();
});
