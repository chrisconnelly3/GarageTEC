import { describe, it, expect } from "vitest";
import { phaseAtTime, phaseMoments } from "./phase";
import type { Moment } from "./types";

const m = (kind: string, time_s: number): Moment =>
  ({ id: 0, swing_id: 1, kind, view: null, frame_index: null, time_s });

describe("phaseAtTime", () => {
  const moments = [m("address", 0), m("top", 1.0), m("impact", 1.5)];
  it("returns the latest phase whose time <= t", () => {
    expect(phaseAtTime(moments, 0.5)).toBe("address");
    expect(phaseAtTime(moments, 1.2)).toBe("top");
    expect(phaseAtTime(moments, 2.0)).toBe("impact");
  });
  it("before the first moment -> the first phase", () => {
    expect(phaseAtTime(moments, -1)).toBe("address");
  });
  it("no card-phase moments -> defaults to impact", () => {
    expect(phaseAtTime([], 0)).toBe("impact");
  });
  it("phaseMoments keeps only address/top/impact, time-ordered", () => {
    const out = phaseMoments([m("impact", 1.5), m("takeaway", 0.3), m("top", 1.0), m("address", 0)]);
    expect(out.map((x) => x.kind)).toEqual(["address", "top", "impact"]);
  });
});
