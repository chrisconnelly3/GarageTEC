export const METRIC_LABEL: Record<string, string> = {
  shoulder_tilt_deg: "Shoulder Tilt", hip_tilt_deg: "Hip Tilt",
  shoulder_turn_deg: "Shoulder Turn", hip_turn_deg: "Hip Turn",
  spine_angle_deg: "Spine Angle", hand_depth_in: "Hand Depth",
  early_extension_in: "Early Ext.", hip_sway_in: "Hip Sway",
  head_sway_in: "Head Sway",
};
// (min,max) ideal ranges used by MetricCard.idealRange
export const METRIC_IDEAL: Record<string, [number, number]> = {
  shoulder_tilt_deg: [35, 45], hip_tilt_deg: [8, 16], shoulder_turn_deg: [90, 110],
  hip_turn_deg: [40, 55], spine_angle_deg: [40, 45], hand_depth_in: [12, 16],
  early_extension_in: [0, 1], hip_sway_in: [0, 2], head_sway_in: [0, 1.5],
};
// which direction is "good" for MetricCard.deltaGood
export const METRIC_GOOD: Record<string, "up" | "down" | "neutral"> = {
  shoulder_tilt_deg: "up", hip_tilt_deg: "neutral", shoulder_turn_deg: "up",
  hip_turn_deg: "up", spine_angle_deg: "neutral", hand_depth_in: "up",
  early_extension_in: "down", hip_sway_in: "down", head_sway_in: "down",
};
export const labelFor = (name: string) => METRIC_LABEL[name] ?? name;
export const isEstimated = (method?: string | null) =>
  !!method && method.includes("confidence=low");
export const heightToFtIn = (inches: number) =>
  `${Math.floor(inches / 12)}' ${Math.round(inches % 12)}"`;
// baseline = mean of all but the latest history point; delta = latest - baseline
export function deltaVsBaseline(points: { value: number }[]): { value: number; delta: number } {
  if (points.length === 0) return { value: 0, delta: 0 };
  const latest = points[points.length - 1].value;
  const prior = points.slice(0, -1);
  if (prior.length === 0) return { value: latest, delta: 0 };
  const base = prior.reduce((s, p) => s + p.value, 0) / prior.length;
  return { value: latest, delta: Math.round((latest - base) * 10) / 10 };
}
