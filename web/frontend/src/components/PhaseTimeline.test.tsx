import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PhaseTimeline } from "./PhaseTimeline";

describe("PhaseTimeline", () => {
  it("renders the 8 phases and marks present ones, fires onSeek with the kind", () => {
    const onSeek = vi.fn();
    render(<PhaseTimeline present={new Set(["Address", "Top", "Impact"])}
      active="Top" onSeek={onSeek} />);
    expect(screen.getByText("Address")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Impact"));
    expect(onSeek).toHaveBeenCalledWith("Impact");
  });
});
