import { describe, it, expect, vi, afterEach } from "vitest";
import { buildHistoryUrl, startSession, endSession } from "./api";
import { deltaVsBaseline, isEstimated, labelFor, heightToFtIn, METRIC_IDEAL, withinTimeframe, timeframeCutoff } from "./format";

describe("session endpoints", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("startSession POSTs to /api/capture/start-session and returns status", async () => {
    const status = { session_active: true, active_session_id: 5 };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve(status),
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(startSession()).resolves.toEqual(status);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/capture/start-session",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("startSession rejects with a 409-prefixed error when no player is active", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409 }));
    await expect(startSession()).rejects.toThrow(/^409/);
  });

  it("endSession POSTs to /api/capture/end-session", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve({ session_active: false }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await endSession();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/capture/end-session",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("api/format helpers", () => {
  it("buildHistoryUrl defaults context to impact (NOT overall)", () => {
    expect(buildHistoryUrl(1, "hip_sway_in")).toContain("context=impact");
    expect(buildHistoryUrl(1, "hip_sway_in")).not.toContain("overall");
  });
  it("deltaVsBaseline compares latest to mean of prior", () => {
    expect(deltaVsBaseline([{ value: 2 }, { value: 4 }, { value: 6 }]).delta).toBe(3); // 6 - mean(2,4)=3
    expect(deltaVsBaseline([{ value: 5 }]).delta).toBe(0);
    expect(deltaVsBaseline([]).value).toBe(0);
  });
  it("isEstimated flags low-confidence methods", () => {
    expect(isEstimated("foreshortening_2d;confidence=low")).toBe(true);
    expect(isEstimated("exact")).toBe(false);
  });
  it("labels + height + ideal map", () => {
    expect(labelFor("hip_sway_in")).toBe("Hip Sway");
    expect(heightToFtIn(72)).toBe("6' 0\"");
    expect(METRIC_IDEAL.hip_sway_in).toEqual([0, 2]);
  });
});

describe("withinTimeframe", () => {
  const now = new Date("2026-06-04T12:00:00Z");
  const pts = [
    { created_at: "2026-06-04T06:00:00Z", value: 1 }, // 6h ago
    { created_at: "2026-05-30T12:00:00Z", value: 2 }, // 5d ago
    { created_at: "2026-01-01T12:00:00Z", value: 3 }, // ~5mo ago
  ];
  it("Session keeps only the last 12h", () => {
    expect(withinTimeframe(pts, "Session", now).map(p => p.value)).toEqual([1]);
  });
  it("Week keeps last 7 days", () => {
    expect(withinTimeframe(pts, "Week", now).map(p => p.value)).toEqual([1, 2]);
  });
  it("Year keeps all three", () => {
    expect(withinTimeframe(pts, "Year", now).map(p => p.value)).toEqual([1, 2, 3]);
  });
  it("cutoff is monotonic across spans", () => {
    expect(timeframeCutoff("Session", now).getTime())
      .toBeGreaterThan(timeframeCutoff("Year", now).getTime());
  });
});
