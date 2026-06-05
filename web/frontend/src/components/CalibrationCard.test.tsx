// web/frontend/src/components/CalibrationCard.test.tsx
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CalibrationCard } from "./CalibrationCard";

vi.mock("../lib/api", () => ({
  startCalibration: vi.fn(async () => ({ ok: true })),
  stopCalibration: vi.fn(async () => ({ ok: true })),
  runCalibration: vi.fn(async () => ({ ok: true, n_poses: 12, reprojection_error: 0.4 })),
  getCalibrationStatus: vi.fn(async () => ({ capturing: false, good_poses: 0, coverage: [], device_index: 0, cols: 9, rows: 6 })),
  getActiveCalibration: vi.fn(async () => null),
  getCalibrationHistory: vi.fn(async () => []),
  activateCalibration: vi.fn(async () => ({ ok: true })),
  getCameras: vi.fn(async () => [
    { index: 0, name: "Cam Zero" }, { index: 1, name: "Cam One" },
  ]),
}));

// Capture the SSE handlers so tests can simulate status events.
const sse = vi.hoisted(() => ({ handlers: {} as any }));
vi.mock("../lib/useCalibrationSse", () => ({
  useCalibrationSse: (_active: boolean, handlers: any) => { sse.handlers = handlers; },
}));

describe("CalibrationCard", () => {
  beforeEach(() => vi.clearAllMocks());
  it("renders title and start button", async () => {
    render(<CalibrationCard />);
    expect(screen.getByText(/Camera Calibration/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Start/i })).toBeTruthy();
  });
  it("calls startCalibration on Start", async () => {
    const api = await import("../lib/api");
    render(<CalibrationCard />);
    fireEvent.click(screen.getByRole("button", { name: /Start/i }));
    expect(api.startCalibration).toHaveBeenCalled();
  });
  it("renders history section heading", async () => {
    const api = await import("../lib/api");
    vi.mocked(api.getCalibrationHistory).mockResolvedValueOnce([
      { id: 7, created_at: "2025-01-01T00:00:00", n_poses: 20, reprojection_error: 0.31, is_active: 1 },
      { id: 5, created_at: "2024-12-01T00:00:00", n_poses: 15, reprojection_error: 0.55, is_active: 0 },
    ]);
    render(<CalibrationCard />);
    // heading is always rendered
    expect(screen.getByText(/History/i)).toBeTruthy();
  });
  it("auto-runs calibration when the varied-pose target is reached", async () => {
    const api = await import("../lib/api");
    render(<CalibrationCard />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Start Capture/i }));
    });
    // SSE reports target reached (24 varied poses) -> auto-run once
    await act(async () => {
      sse.handlers.calibration_status({
        good_poses: 24, target_poses: 24, min_poses: 15, tilt_buckets: 5, coverage: [] });
    });
    await waitFor(() => expect(api.runCalibration).toHaveBeenCalledTimes(1));
  });
  it("does NOT auto-run before the target", async () => {
    const api = await import("../lib/api");
    render(<CalibrationCard />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Start Capture/i }));
    });
    await act(async () => {
      sse.handlers.calibration_status({
        good_poses: 14, target_poses: 24, min_poses: 15, tilt_buckets: 3, coverage: [] });
    });
    expect(api.runCalibration).not.toHaveBeenCalled();
  });
});
