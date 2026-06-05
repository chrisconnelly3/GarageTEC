import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SwingReplay } from "./SwingReplay";

describe("SwingReplay", () => {
  it("renders a <video> with the source when src is provided", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" />);
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video?.getAttribute("src")).toBe("/media/swings/x.mp4");
  });
  it("falls back to the placeholder when no src", () => {
    const { container } = render(<SwingReplay src={null} />);
    expect(container.querySelector("video")).toBeNull();
  });
});
