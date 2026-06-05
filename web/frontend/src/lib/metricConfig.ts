// Display metadata for the metric cards. Thresholds/zones live server-side; this
// file only decides which metrics are cards, their order, and grouping.

export const PHASES = ["address", "top", "impact"] as const;
export type Phase = (typeof PHASES)[number];

export const BODY_CARD_ORDER = [
  "shoulder_tilt_deg",
  "hip_tilt_deg",
  "spine_angle_deg",
  "shoulder_turn_deg",
  "hip_turn_deg",
  "x_factor_deg",
  "x_factor_stretch_deg",
  "hip_sway_in",
  "head_sway_in",
  "early_extension_in",
  "hand_depth_in", // raw (no tour ref yet)
];

export const BALL_BENCHMARK_ORDER = [
  "ball_speed", "club_speed", "smash", "carry", "launch", "spin", "attack_angle",
];
export const BALL_RAW_ORDER = [
  "club_path", "face_to_target", "spin_axis", "back_spin", "side_spin", "hla",
];
export const BALL_CARD_ORDER = [...BALL_BENCHMARK_ORDER, ...BALL_RAW_ORDER];

export const METRIC_UNIT: Record<string, string> = {
  x_factor_deg: "deg", x_factor_stretch_deg: "deg",
};
