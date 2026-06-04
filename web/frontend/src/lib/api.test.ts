import { describe, it, expect } from "vitest";
import { buildHistoryUrl } from "./api";
import { deltaVsBaseline, isEstimated, labelFor, heightToFtIn, METRIC_IDEAL, withinTimeframe, timeframeCutoff } from "./format";

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
