// web/frontend/src/lib/calibration.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { startCalibration, runCalibration, getCalibrationStatus } from "./api";

describe("calibration api", () => {
  beforeEach(() => {
    global.fetch = vi.fn(async (url: string, opts?: any) => ({
      ok: true, status: 200,
      json: async () => ({ url, body: opts?.body ? JSON.parse(opts.body) : null }),
    })) as any;
  });
  it("posts start with params", async () => {
    const r: any = await startCalibration({ device_index: 0, cols: 9, rows: 6, square_mm: 25 });
    expect(r.url).toBe("/api/calibration/start");
    expect(r.body.cols).toBe(9);
  });
  it("runs and reads status", async () => {
    expect((await runCalibration() as any).url).toBe("/api/calibration/run");
    expect((await getCalibrationStatus() as any).url).toBe("/api/calibration/status");
  });
});
