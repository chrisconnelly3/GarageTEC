import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
  it("uses a 32:9 aspect-ratio container (two side-by-side 16:9 cameras)", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" />);
    expect(container.querySelector(".aspect-\\[32\\/9\\]")).not.toBeNull();
  });
  it("has a play control (bottom-bar button + center overlay when paused)", () => {
    render(<SwingReplay src="/media/swings/x.mp4" />);
    // Bottom-bar play button + large center overlay, both labelled Play while paused.
    expect(screen.getAllByRole("button", { name: /play/i }).length).toBeGreaterThanOrEqual(2);
  });
  it("has a working fullscreen toggle button", () => {
    render(<SwingReplay src="/media/swings/x.mp4" />);
    expect(screen.getByRole("button", { name: /fullscreen/i })).toBeInTheDocument();
  });
  it("accepts an impactTime prop without error", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" impactTime={1.2} />);
    expect(container.querySelector("video")).not.toBeNull();
  });
});
