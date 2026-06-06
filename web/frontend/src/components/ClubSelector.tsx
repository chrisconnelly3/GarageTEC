import { useEffect, useState } from "react";
import { getClubs } from "../lib/api";

/** Live club picker — sets the club being hit so each shot is tagged and the
 *  ball "vs tour" comparison uses the right TrackMan row. */
export function ClubSelector({ value, onChange }:
  { value: string | null; onChange: (club: string | null) => void }) {
  const [clubs, setClubs] = useState<string[]>([]);
  useEffect(() => { getClubs().then(setClubs).catch(() => {}); }, []);
  return (
    <div className="flex items-center gap-3">
      <label className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">
        Club
      </label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-2 text-[#E7EEE9] outline-none min-h-[44px] focus-visible:ring-2 focus-visible:ring-garage-green/60 focus-visible:border-garage-green"
      >
        <option value="">Select club…</option>
        {clubs.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
    </div>
  );
}
