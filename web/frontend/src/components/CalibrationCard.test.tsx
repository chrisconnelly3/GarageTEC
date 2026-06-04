// web/frontend/src/components/CalibrationCard.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CalibrationCard } from "./CalibrationCard";

vi.mock("../lib/api", () => ({
  startCalibration: vi.fn(async () => ({ ok: true })),
  stopCalibration: vi.fn(async () => ({ ok: true })),
  runCalibration: vi.fn(async () => ({ ok: true, n_poses: 12, reprojection_error: 0.4 })),
  getCalibrationStatus: vi.fn(async () => ({ capturing: false, good_poses: 0, coverage: [], device_index: 0, cols: 9, rows: 6 })),
  getActiveCalibration: vi.fn(async () => null),
}));
vi.mock("../lib/useCalibrationSse", () => ({ useCalibrationSse: () => {} }));

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
});
