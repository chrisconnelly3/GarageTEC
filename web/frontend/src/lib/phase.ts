import type { Moment } from "./types";
import { PHASES, type Phase } from "./metricConfig";

/** Keep only the card phases (address/top/impact) that have a timestamp, ordered. */
export function phaseMoments(moments: Moment[]): Moment[] {
  return PHASES
    .map((p) => moments.find((m) => m.kind === p && m.time_s != null))
    .filter((m): m is Moment => !!m);
}

/** The current card phase at playback time t = the latest card-phase moment whose
 *  time_s <= t. Falls back to the first available phase, or "impact" if none. */
export function phaseAtTime(moments: Moment[], t: number): Phase {
  const pm = phaseMoments(moments);
  if (pm.length === 0) return "impact";
  let current = pm[0];
  for (const mt of pm) {
    if ((mt.time_s as number) <= t) current = mt;
  }
  return current.kind as Phase;
}
