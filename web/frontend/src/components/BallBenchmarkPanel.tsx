import type { BallBenchmark } from "../lib/types";

function fmt(v: number, unit: string): string {
  const r = unit === "rpm" ? Math.round(v) : Math.round(v * 10) / 10;
  return unit === "deg" ? `${r}°` : unit ? `${r} ${unit}` : `${r}`;
}

/** Ball-data "vs ideal" panel — the R50's reported ball/club metrics against the
 *  TrackMan PGA Tour averages for the selected club. Only metrics the R50 passes
 *  over Open Connect appear; Max Height / Land Angle aren't in the protocol. */
export function BallBenchmarkPanel({ ball, club }:
  { ball: BallBenchmark[]; club: string | null }) {
  return (
    <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-[#E7EEE9]">Ball vs Tour Pro</h3>
        <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">
          {club ? `${club} · TrackMan avg` : "TrackMan avg"}
        </span>
      </div>

      {ball.length === 0 ? (
        <p className="text-sm text-[#8B978F]">
          {club ? "No matched ball data for this shot yet."
                : "Select the club you're hitting (top of Live) to compare ball data."}
        </p>
      ) : (
        <ul className="space-y-2">
          {ball.map((b) => (
            <li key={b.key}
                className="flex items-center justify-between rounded-xl bg-[#1A211D] px-3 py-2">
              <span className="text-sm text-[#E7EEE9]">{b.label}</span>
              <div className="flex items-center gap-3 text-sm font-mono shrink-0">
                <span className="text-[#E7EEE9]">{fmt(b.value, b.unit)}</span>
                <span className="text-[#8B978F]">/ {fmt(b.target, b.unit)}</span>
                <span className={b.near ? "text-garage-green" : "text-[#E7EEE9]"}>
                  {b.delta >= 0 ? "+" : ""}{fmt(b.delta, b.unit)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
