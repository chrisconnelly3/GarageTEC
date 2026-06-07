import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SwingControlBar } from "./SwingControlBar";

const base = {
  following: true,
  newCount: 0,
  r50: "connected" as const,
  label: "Latest · 7i · 2:14",
  swings: [
    { id: 42, created_at: "2024-01-01T10:02:00Z", club: "7 Iron", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
    { id: 41, created_at: "2024-01-01T10:01:00Z", club: "Driver", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
  ],
  currentSwingId: 42,
  canPrev: true,
  canNext: false,
  onGoLive: vi.fn(),
  onPrev: vi.fn(),
  onNext: vi.fn(),
  onPickSwing: vi.fn(),
};

describe("SwingControlBar", () => {
  it("shows a solid LIVE pill when following + connected", () => {
    render(<SwingControlBar {...base} />);
    const pill = screen.getByTestId("live-pill");
    expect(pill.className).toContain("bg-garage-green");
    expect(pill.textContent).toMatch(/LIVE/);
  });

  it("shows an outline pill with the new-shot count when pinned", () => {
    render(<SwingControlBar {...base} following={false} newCount={2} currentSwingId={41} canNext />);
    const pill = screen.getByTestId("live-pill");
    expect(pill.className).not.toContain("bg-garage-green");
    expect(screen.getByTestId("new-count").textContent).toBe("2");
  });

  it("calls onGoLive when the pill is tapped while pinned", () => {
    const onGoLive = vi.fn();
    render(<SwingControlBar {...base} following={false} onGoLive={onGoLive} />);
    fireEvent.click(screen.getByTestId("live-pill"));
    expect(onGoLive).toHaveBeenCalled();
  });

  it("calls onPrev / onNext from the arrows and respects disabled", () => {
    const onPrev = vi.fn(), onNext = vi.fn();
    render(<SwingControlBar {...base} onPrev={onPrev} onNext={onNext} canPrev canNext={false} />);
    fireEvent.click(screen.getByLabelText("Older swing"));
    fireEvent.click(screen.getByLabelText("Newer swing"));
    expect(onPrev).toHaveBeenCalled();
    expect(onNext).not.toHaveBeenCalled(); // disabled
  });

  it("picks a swing from the dropdown", () => {
    const onPickSwing = vi.fn();
    render(<SwingControlBar {...base} onPickSwing={onPickSwing} />);
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "41" } });
    expect(onPickSwing).toHaveBeenCalledWith(41);
  });
});
