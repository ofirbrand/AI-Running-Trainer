import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { InfoTip } from "./InfoTip";

describe("InfoTip", () => {
  it("renders a trigger when content is provided", () => {
    render(<InfoTip text="Helpful explanation" label="What is this" />);
    expect(screen.getByRole("button", { name: "What is this" })).toBeInTheDocument();
  });

  it("renders nothing when there is no content", () => {
    const { container } = render(<InfoTip term="nonexistent_term_xyz" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("resolves content from the info dictionary by term", () => {
    render(<InfoTip term="vo2max" />);
    expect(screen.getByRole("button", { name: "More information" })).toBeInTheDocument();
  });
});
