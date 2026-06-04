import { describe, it, expect } from "vitest";
import { buildHistoryUrl } from "./api";
import { deltaVsBaseline, isEstimated, labelFor, heightToFtIn, METRIC_IDEAL } from "./format";

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
