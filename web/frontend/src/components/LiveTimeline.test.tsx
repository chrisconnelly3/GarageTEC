import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LiveTimeline } from "./LiveTimeline";
import type { Moment } from "../lib/types";

const moments: Moment[] = [
  { id: 1, swing_id: 1, kind: "address", view: null, frame_index: 0, time_s: 0 },
  { id: 2, swing_id: 1, kind: "top", view: null, frame_index: 15, time_s: 1.0 },
  { id: 3, swing_id: 1, kind: "impact", view: null, frame_index: 30, time_s: 2.0 },
];

describe("LiveTimeline", () => {
  it("positions each phase marker at time_s / duration along the track", () => {
    render(
      <LiveTimeline moments={moments} duration={4} currentTime={0} activeLabel="Address" onSeek={() => {}} />,
    );
    // address @0/4 = 0%, top @1/4 = 25%, impact @2/4 = 50%.
    expect(screen.getByTestId("marker-Address").getAttribute("data-pct")).toBe("0.00");
    expect(screen.getByTestId("marker-Top").getAttribute("data-pct")).toBe("25.00");
    expect(screen.getByTestId("marker-Impact").getAttribute("data-pct")).toBe("50.00");
  });

  it("places the playhead at currentTime / duration", () => {
    render(
      <LiveTimeline moments={moments} duration={4} currentTime={1} activeLabel="Address" onSeek={() => {}} />,
    );
    const head = screen.getByTestId("live-playhead") as HTMLElement;
    expect(head.style.left).toBe("25%");
  });

  it("seeks the video to the marker's time_s when a marker is tapped", () => {
    const onSeek = vi.fn();
    render(
      <LiveTimeline moments={moments} duration={4} currentTime={0} activeLabel="Address" onSeek={onSeek} />,
    );
    fireEvent.click(screen.getByTestId("marker-Impact"));
    expect(onSeek).toHaveBeenCalledWith(2.0, "Impact");
  });

  it("highlights the active marker (current phase)", () => {
    render(
      <LiveTimeline moments={moments} duration={4} currentTime={2} activeLabel="Impact" onSeek={() => {}} />,
    );
    // Active marker dot is the larger highlighted variant.
    const dot = screen.getByTestId("marker-Impact").querySelector("span");
    expect(dot?.className).toContain("bg-garage-green");
    expect(dot?.className).toContain("w-4");
  });

  it("ignores markers without a timestamp", () => {
    const partial: Moment[] = [
      ...moments,
      { id: 4, swing_id: 1, kind: "takeaway", view: null, frame_index: null, time_s: null },
    ];
    render(
      <LiveTimeline moments={partial} duration={4} currentTime={0} activeLabel="Address" onSeek={() => {}} />,
    );
    expect(screen.queryByTestId("marker-Takeaway")).toBeNull();
  });
});
