import type { Benchmark } from "../lib/types";

const LABELS: Record<string, string> = {
  shoulder_tilt_deg: "Shoulder tilt",
  hip_tilt_deg: "Hip tilt",
  spine_angle_deg: "Spine angle",
  shoulder_turn_deg: "Shoulder turn",
  hip_turn_deg: "Hip turn",
  x_factor_deg: "X-factor",
  x_factor_stretch_deg: "X-factor stretch",
  hip_sway_in: "Hip sway",
  head_sway_in: "Head sway",
};
const PHASE: Record<string, string> = {
  address: "Address", top: "Top", impact: "Impact",
  finish: "Finish", downswing: "Downswing",
};

function fmt(v: number, unit: string | null): string {
  const r = Math.round(v * 10) / 10;
  return unit === "deg" ? `${r}°` : unit === "in" ? `${r}"` : `${r}`;
}

/** "vs Tour Pro" panel — each computed metric against its GolfTEC tour target,
 *  honoring the 2D/3D gate (rotation/side-bend at top/impact show "needs 3D"
 *  until the bay cameras are calibrated). */
export function BenchmarkPanel({ benchmarks }: { benchmarks: Benchmark[] }) {
  return (
    <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-[#E7EEE9]">vs Tour Pro</h3>
        <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">GolfTEC avg</span>
      </div>

      {benchmarks.length === 0 ? (
        <p className="text-sm text-[#8B978F]">No tour-pro comparisons for this swing yet.</p>
      ) : (
        <ul className="space-y-2">
          {benchmarks.map((b) => {
            const label = LABELS[b.name] ?? b.name;
            const phase = PHASE[b.context] ?? b.context;
            const within = b.delta != null && Math.abs(b.delta) <= 5;
            return (
              <li key={`${b.name}-${b.context}`}
                  className="flex items-center justify-between rounded-xl bg-[#1A211D] px-3 py-2">
                <div className="min-w-0">
                  <div className="text-sm text-[#E7EEE9] truncate">{label}</div>
                  <div className="text-[10px] uppercase tracking-wider text-[#8B978F]">{phase}</div>
                </div>
                <div className="flex items-center gap-3 text-sm font-mono shrink-0">
                  <span className="text-[#E7EEE9]">{fmt(b.value, b.unit)}</span>
                  <span className="text-[#8B978F]">/ {fmt(b.target, b.unit)}</span>
                  {b.comparable ? (
                    <span className={within ? "text-garage-green" : "text-[#E7EEE9]"}>
                      {b.delta != null && b.delta >= 0 ? "+" : ""}{b.delta != null ? fmt(b.delta, b.unit) : ""}
                    </span>
                  ) : (
                    <span className="text-[10px] font-sans uppercase tracking-wider text-[#8B978F] bg-[#0A0D0B] rounded px-2 py-0.5">
                      needs 3D
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {benchmarks.some((b) => !b.comparable) && (
        <p className="mt-3 text-[11px] text-[#8B978F]">
          "needs 3D" metrics (turn, X-factor, side-bend at top/impact) light up once
          the two bay cameras are calibrated. The rest compare from 2D today.
        </p>
      )}
    </div>
  );
}
