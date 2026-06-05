import type { MetricDirection } from "./types";

const WINDOW = 10; // rolling-average window of recent prior swings

export interface Trend {
  delta: number;          // current - rolling avg (sign = arrow direction)
  towardPro: boolean | null; // did the move go toward the target? null if unknown
}

/** points: prior values (most recent last is fine; only the last WINDOW are used,
 *  EXCLUDING the current swing). current: this swing's value. target/direction:
 *  for the toward/away color (null target -> towardPro null). */
export function computeTrend(
  points: { value: number }[],
  current: number,
  target: number | null,
  direction: MetricDirection | null,
): Trend {
  const prior = points.slice(-WINDOW);
  if (prior.length === 0) return { delta: 0, towardPro: null };
  const avg = prior.reduce((s, p) => s + p.value, 0) / prior.length;
  const delta = Math.round((current - avg) * 100) / 100;
  if (target == null || direction == null) return { delta, towardPro: null };

  const dist = (v: number) => {
    if (direction === "higher") return Math.max(0, target - v);
    if (direction === "lower") return Math.max(0, v - target);
    return Math.abs(v - target); // match, range
  };
  if (delta === 0) return { delta, towardPro: null };
  return { delta, towardPro: dist(current) < dist(avg) };
}
