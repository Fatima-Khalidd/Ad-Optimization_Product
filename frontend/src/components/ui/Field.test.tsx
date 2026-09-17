import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Field from "./Field";

describe("Field", () => {
  it("carries a visible focus-ring class alongside the border colour change", () => {
    render(<Field label="Email" name="email" />);

    const input = screen.getByLabelText("Email");
    expect(input.className).toContain("focus-visible:ring-1");
    expect(input.className).toContain("focus-visible:ring-teal");
  });
});
