export const METRIC_LABEL: Record<string, string> = {
  shoulder_tilt_deg: "Shoulder Tilt", hip_tilt_deg: "Hip Tilt",
  shoulder_turn_deg: "Shoulder Turn", hip_turn_deg: "Hip Turn",
  spine_angle_deg: "Spine Angle", hand_depth_in: "Hand Depth",
  early_extension_in: "Early Ext.", hip_sway_in: "Hip Sway",
  head_sway_in: "Head Sway",
  x_factor_deg: "X-Factor", x_factor_stretch_deg: "X-Factor Stretch",
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
// Body-metric units are encoded in the key suffix (_deg → °, _in → ").
export const unitForMetric = (name: string) =>
  name.endsWith("_deg") ? "°" : name.endsWith("_in") ? '"' : "";

// --- History chart axis helpers (shared by the body + ball charts) ---
export const shortDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};
export const timeOfDay = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
};
/** True when every ISO string falls on the same calendar date (YYYY-MM-DD). */
export const allSameDay = (isos: string[]): boolean => {
  if (isos.length < 2) return false;
  const day0 = isos[0].slice(0, 10);
  return isos.every((s) => s.slice(0, 10) === day0);
};

// History charts plot one point per shot, so consecutive shots share a date label.
// Return the data indices at which the label first changes (one tick per day),
// evenly sampled down to `max` so a long timeframe never crowds the axis.
export function labelChangeTicks(labels: string[], max = 8): number[] {
  const starts: number[] = [];
  labels.forEach((l, i) => {
    if (i === 0 || l !== labels[i - 1]) starts.push(i);
  });
  if (starts.length <= max) return starts;
  const step = Math.ceil(starts.length / max);
  return starts.filter((_, i) => i % step === 0);
}

// Ball-metric trends (History → Ball section). `metric` keys match /api/ball-history
// (which mirror the ball benchmark keys). `good` is the direction that's better;
// "neutral" metrics (launch/spin/attack) are shown vs the tour target, not as good/bad.
export interface BallMetricDef {
  key: string; label: string; unit: string; good: "up" | "down" | "neutral"; decimals: number;
}
export const BALL_METRICS: BallMetricDef[] = [
  { key: "ball_speed", label: "Ball Speed", unit: "mph", good: "up", decimals: 1 },
  { key: "club_speed", label: "Club Speed", unit: "mph", good: "up", decimals: 1 },
  { key: "smash", label: "Smash Factor", unit: "", good: "up", decimals: 2 },
  { key: "carry", label: "Carry", unit: "yds", good: "up", decimals: 1 },
  { key: "launch", label: "Launch Angle", unit: "deg", good: "neutral", decimals: 1 },
  { key: "spin", label: "Spin Rate", unit: "rpm", good: "neutral", decimals: 0 },
  { key: "attack_angle", label: "Attack Angle", unit: "deg", good: "neutral", decimals: 1 },
];

export type Timeframe = "Session" | "Week" | "Month" | "Year";

// Returns the cutoff Date for a timeframe relative to `now`. "Session" uses a
// 12-hour window (one bay session); Week/Month/Year are calendar-ish spans.
export function timeframeCutoff(tf: Timeframe, now = new Date()): Date {
  const d = new Date(now);
  switch (tf) {
    case "Session": d.setHours(d.getHours() - 12); break;
    case "Week": d.setDate(d.getDate() - 7); break;
    case "Month": d.setMonth(d.getMonth() - 1); break;
    case "Year": d.setFullYear(d.getFullYear() - 1); break;
  }
  return d;
}

export function withinTimeframe<T extends { created_at: string }>(
  points: T[], tf: Timeframe, now = new Date(),
): T[] {
  const cutoff = timeframeCutoff(tf, now).getTime();
  return points.filter((p) => {
    const t = new Date(p.created_at).getTime();
    return Number.isNaN(t) ? true : t >= cutoff;
  });
}

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
