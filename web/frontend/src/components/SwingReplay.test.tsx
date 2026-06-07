import { describe, it, expect, vi } from "vitest";
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
  it("uses a 32:9 aspect-ratio container by default (two side-by-side 16:9 cameras)", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" />);
    expect(container.querySelector(".aspect-\\[32\\/9\\]")).not.toBeNull();
  });
  it("in fill mode drops the hard aspect lock and fills the column (object-contain keeps real aspect)", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" fill />);
    // No fixed 32:9 box — the area flexes to fill instead.
    expect(container.querySelector(".aspect-\\[32\\/9\\]")).toBeNull();
    const video = container.querySelector("video");
    expect(video?.className).toContain("object-contain");
  });
  it("loops the video so it replays until paused", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" />);
    const video = container.querySelector("video") as HTMLVideoElement;
    expect(video.loop).toBe(true);
  });
  it("defaults the speed toggle to Slow-mo (selected) with Slow-mo listed before Realtime", () => {
    render(<SwingReplay src="/media/swings/x.mp4" />);
    const slow = screen.getByRole("button", { name: /slow-mo/i });
    const real = screen.getByRole("button", { name: /^realtime$/i });
    // Slow-mo is the selected (highlighted) speed on load.
    expect(slow.className).toContain("bg-[#242C27]");
    expect(real.className).not.toContain("bg-[#242C27]");
    // Slow-mo appears before Realtime in DOM order.
    expect(slow.compareDocumentPosition(real) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("reports duration via onDuration when metadata loads", () => {
    const onDuration = vi.fn();
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" onDuration={onDuration} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    Object.defineProperty(video, "duration", { value: 2.4, configurable: true });
    video.dispatchEvent(new Event("loadedmetadata"));
    expect(onDuration).toHaveBeenCalledWith(2.4);
  });
  it("has a play control (bottom-bar button + center overlay when paused)", () => {
    render(<SwingReplay src="/media/swings/x.mp4" />);
    // Bottom-bar play button + large center overlay, both labelled Play while paused.
    expect(screen.getAllByRole("button", { name: /play/i }).length).toBeGreaterThanOrEqual(2);
  });
  it("in fill mode the bottom bar has NO progress-fill bar (LiveTimeline is the scrubber)", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" fill />);
    // The progress fill div has a style with width: X% driven by progress state.
    // In fill mode it should not be rendered.
    const bars = container.querySelectorAll(".bg-\\[\\#1A211D\\]");
    // The track bar (bg-[#1A211D]) only exists in non-fill mode.
    expect(bars.length).toBe(0);
  });
  it("in fill mode still has a play/pause button in the bottom bar", () => {
    render(<SwingReplay src="/media/swings/x.mp4" fill />);
    // At least the bottom-bar play button must be present (center overlay also present while paused).
    expect(screen.getAllByRole("button", { name: /play/i }).length).toBeGreaterThanOrEqual(1);
  });
  it("has a working fullscreen toggle button", () => {
    render(<SwingReplay src="/media/swings/x.mp4" />);
    expect(screen.getByRole("button", { name: /fullscreen/i })).toBeInTheDocument();
  });
  it("accepts an impactTime prop without error", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" impactTime={1.2} />);
    expect(container.querySelector("video")).not.toBeNull();
  });
  it("shows a custom placeholder when src is null and placeholder is given", () => {
    render(<SwingReplay src={null} placeholder="Video not kept for this swing" />);
    expect(screen.getByText("Video not kept for this swing")).toBeInTheDocument();
  });
});
