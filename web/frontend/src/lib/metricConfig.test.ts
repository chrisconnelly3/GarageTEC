import { describe, it, expect } from "vitest";
import { BODY_CARD_ORDER, BALL_CARD_ORDER, PHASES } from "./metricConfig";

describe("metricConfig", () => {
  it("lists body cards in the agreed order, X-Factor present", () => {
    expect(BODY_CARD_ORDER[0]).toBe("shoulder_tilt_deg");
    expect(BODY_CARD_ORDER).toContain("x_factor_deg");
    expect(BODY_CARD_ORDER).toContain("hand_depth_in");
  });
  it("orders ball benchmarked keys before raw keys", () => {
    expect(BALL_CARD_ORDER.indexOf("ball_speed"))
      .toBeLessThan(BALL_CARD_ORDER.indexOf("club_path"));
  });
  it("exposes the three card phases", () => {
    expect(PHASES).toEqual(["address", "top", "impact"]);
  });
});
