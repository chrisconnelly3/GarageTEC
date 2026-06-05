import { describe, it, expect } from "vitest";
import { computeTrend } from "./trend";

describe("computeTrend", () => {
  it("returns neutral when history is too short", () => {
    expect(computeTrend([], 10, 9, "match")).toEqual({ delta: 0, towardPro: null });
  });
  it("match: moving closer to target is toward (green)", () => {
    const t = computeTrend([{ value: 13 }, { value: 15 }], 11, 10, "match");
    expect(t.delta).toBe(-3); // 11 - 14
    expect(t.towardPro).toBe(true);
  });
  it("higher: increasing is toward regardless of target side", () => {
    const t = computeTrend([{ value: 160 }, { value: 162 }], 168, 167, "higher");
    expect(t.delta).toBe(7); // 168 - 161
    expect(t.towardPro).toBe(true);
  });
  it("lower: decreasing is toward", () => {
    const t = computeTrend([{ value: 3.0 }, { value: 3.2 }], 2.4, 1.6, "lower");
    expect(t.towardPro).toBe(true);
  });
  it("no target (raw) -> toward unknown, still reports delta", () => {
    const t = computeTrend([{ value: 13 }, { value: 14 }], 15, null, "match");
    expect(t.delta).toBe(1.5);
    expect(t.towardPro).toBe(null);
  });
});
