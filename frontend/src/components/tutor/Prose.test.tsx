import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Prose from "./Prose";

test("renders markdown bold and a katex math span", () => {
  const { container } = render(<Prose text={"Try **multiplying**: $3 \\times 4$"} />);
  expect(screen.getByText("multiplying").tagName).toBe("STRONG");
  // rehype-katex emits a .katex element
  expect(container.querySelector(".katex")).not.toBeNull();
});
